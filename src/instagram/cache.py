from errno import ENOENT
import os
import time

from src.database import (
        Database,
        InstagramDatabase,
        InstagramQueueDatabase,
        UniqueConstraintFailed,
)
from src.util import logger


class Cache(object):
    """
    Instagram user cache database handling
    """

    _ig_queue = None

    def __init__(self, user):
        self.user = user

        if not Cache._ig_queue:
            Cache._ig_queue = InstagramQueueDatabase()

    def __str__(self):
        result = [self.__class__.__name__]
        if self.user:
            result.append(self.user)
        return ':'.join(result)

    def __getattr__(self, attr):
        # expose InstagramDatabase methods if they aren't overridden
        try:
            return self.__getattribute__(attr)
        except AttributeError:
            return getattr(self.__cache, attr)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None and exc_value is None and traceback is None:
            self.__cache.commit()
            self.__fetch_cache.commit()

        else:
            logger.id(logger.debug, self,
                    'An error occurred! Rolling back changes ...',
                    exc_info=True,
            )
            self.__cache.rollback()
            self.__fetch_cache.rollback()

    @property
    def __cache(self):
        try:
            return self.__the_cache
        except AttributeError:
            self.__the_cache = InstagramDatabase(self.dbpath)
            return self.__the_cache

    @property
    def __fetch_cache(self):
        """
        In-progress fetch cache used to compare missing database elements
        """
        try:
            return self.__the_inprogress_cache
        except AttributeError:
            self.__the_inprogress_cache = InstagramDatabase(self.seenpath)
            return self.__the_inprogress_cache

    def _get_path(self, basename_fmt):
        basename = basename_fmt.format(self.user)
        path = Database.format_path(InstagramDatabase.PATH, dry_run=False)
        return Database.resolve_path(os.path.join(path, basename))

    @property
    def dbpath(self):
        """
        Returns the resolved path to the user's database file
        """
        return self._get_path('{0}.db')

    @property
    def seenpath(self):
        """
        Returns the resolved path of the user's in-progress fetch database file
        """
        return self._get_path('{0}.fetching.db')

    @property
    def queued_last_id(self):
        return Cache._ig_queue.get_last_id_for(self.user)

    @property
    def is_private(self):
        """
        Returns whether the user's cache is flagged as private if the database
                exists

                or None if the database does not exist
        """
        private = None
        if os.path.exists(self.dbpath):
            private = self.__cache.is_private_account

        return private

    @property
    def is_bad(self):
        """
        Returns whether the user's cache is flagged as bad if the database
                exists

                or None if the database does not exist
        """
        bad = None
        if os.path.exists(self.dbpath):
            bad = self.__cache.is_flagged_as_bad

        return bad

    @property
    def expired(self):
        """
        Returns whether the cache is expired (database age > threshold)

        Returns True if no cached data exists
        """
        from .instagram import Instagram

        expired = False

        try:
            cache_mtime = os.path.getmtime(self.dbpath)
        except OSError as e:
            if e.errno == ENOENT:
                # no cached media
                cache_mtime = 0

            else:
                logger.id(logger.critical, self,
                        'Could not determine if {color_user}\'s media cache'
                        ' is expired! (Failed to stat \'{path}\')',
                        color_user=self.user,
                        path=self.dbpath,
                        exc_info=True,
                )

        else:
            cache_age = time.time() - cache_mtime
            threshold = Instagram._cfg.instagram_cache_expire_time
            expired = cache_age > threshold
            if cache_mtime > 0 and expired:
                logger.id(logger.debug, self,
                        'Cache expired! ({time_age} > {time_expire})',
                        time_age=cache_age,
                        time_expire=threshold,
                )

        return expired

    def enqueue(self, last_id):
        """
        Enqueues the user so that their in-progress fetch can be continued
        later.

        This may happen if instagram becomes ratelimited, is experiencing a
        service outage, or the program is killed during a fetch.

        Returns True if the user was successfully enqueued
        """
        if self.user in Cache._ig_queue:
            queued_last_id = Cache._ig_queue.get_last_id_for(self.user)
            if (
                    # don't queue invalid data (last_id queued but no last_id
                    # fetched) -- ie, don't restart the fetching sequence
                    (queued_last_id and not last_id)
                    # don't re-queue the same data
                    or queued_last_id == last_id
            ):
                logger.id(logger.debug, self,
                        'Skipping enqueue'
                        '\n\tqueued:  {queued}'
                        '\n\tlast_id: {last_id}',
                        queued=queued_last_id,
                        last_id=last_id,
                )
                return

        did_enqueue = False
        msg = ['Queueing']
        if last_id:
            msg.append('@ {last_id}')
        msg.append('...')
        logger.id(logger.debug, self,
                ' '.join(msg),
                last_id=last_id,
        )

        try:
            with Cache._ig_queue:
                # XXX: insert() implicitly calls update
                Cache._ig_queue.insert(self.user, last_id)

        except UniqueConstraintFailed:
            # this shouldn't happen
            msg = [
                    'Attempted to enqueue duplicate instagram user'
                    ' \'{color_user}\''
            ]
            if last_id:
                msg.append('@ {last_id}')

            logger.id(logger.warn, self,
                    ' '.join(msg),
                    color_user=self.user,
                    last_id=last_id,
                    exc_info=True,
            )

        else:
            did_enqueue = True
        return did_enqueue

    def insert(self, item):
        """
        Inserts the given media item into the cache.

        This is intended to be called during the fetch.
        """
        try:
            self.__cache.insert(item)
        except UniqueConstraintFailed:
            self.__cache.update(item)

        try:
            self.__fetch_cache.insert(item)
        except UniqueConstraintFailed:
            # this shouldn't happen
            logger.id(logger.debug, self,
                    'Already saw \'{code}\' (was \'{path}\' not deleted?)',
                    code=item['code'],
                    path=self.seenpath,
            )

    def update(self, item):
        # override the update method since insert has update baked in
        pass

    def finish(self):
        """
        This method handles the cleanup/conclusion of an in-progress fetch.
        """
        self._prune_missing()
        self._remove_fetch_cache()
        # remove any queued instagram data for the user, if any
        if self.user in Cache._ig_queue:
            with Cache._ig_queue:
                Cache._ig_queue.delete(self.user)

    def _prune_missing(self):
        """
        Removes extraneous elements in the cache that were not seen during
        the most recent fetch.

        This assumes that the fetch database is transient (that is it is
        only used during and immediately after a single fetch)
        """
        if not os.path.exists(self.seenpath):
            # nothing to prune: the in-progress fetch database doesn't exist
            return

        cached_codes = self.__cache.get_all_codes()
        fetched_codes = self.__fetch_cache.get_all_codes()
        missing = cached_codes - fetched_codes

        logger.id(logger.info, self,
                'Fetched #{num} item{plural}',
                num=len(fetched_codes),
                plural=('' if len(fetched_codes) == 1 else 's'),
        )

        if missing:
            logger.id(logger.debug, self,
                    '\ncached:  #{num_cached}'
                    '\nfetched: #{num_fetched}',
                    num_cached=len(cached_codes),
                    num_fetched=len(fetched_codes),
            )
            logger.id(logger.info, self,
                    '#{num} item{plural} missing: pruning ...',
                    num=len(missing),
                    plural=('' if len(missing) == 1 else 's'),
            )
            logger.id(logger.debug, self,
                    'missing codes:\n\n{color}\n\n',
                    color=missing,
            )

            with self.__cache:
                self.__cache.delete(missing)

    def _remove_fetch_cache(self):
        """
        Removes the in-progress fetch cache. This should be called once the
        fetch has completed.
        """
        removed = False
        if os.path.exists(self.seenpath):
            try:
                self.__the_inprogress_cache.close()
            except AttributeError:
                pass

            logger.id(logger.debug, self,
                    'Removing \'{path}\' ...',
                    path=self.seenpath,
            )

            try:
                os.remove(self.seenpath)
            except (IOError, OSError):
                logger.id(logger.warn, self,
                        'Could not remove \'{path}\'!',
                        path=self.seenpath,
                        exc_info=True,
                )

            else:
                removed = True

        return removed


__all__ = [
        'Cache',
]

