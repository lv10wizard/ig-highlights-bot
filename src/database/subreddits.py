from contextlib import contextmanager
import os
import time

from six import string_types

from ._database import (
        Database,
        UniqueConstraintFailed,
)
from constants import SUBREDDITS_DEFAULTS_PATH
from src.util import logger


class SubredditsDatabase(Database):
    """
    Storage of subreddits to fetch comment streams from
    """

    PATH = 'subreddits.db'

    def __init__(self, do_seed=None, *args, **kwargs):
        Database.__init__(self, *args, **kwargs)

        if do_seed is None:
            do_seed = not os.path.exists(self._resolved_path)
        self.do_seed = bool(do_seed)

    @property
    def _db(self):
        db = Database._db.fget(self)
        try:
            # test if we've cached the file's mtime
            self.__mtime

        except AttributeError:
            self.__mtime = os.stat(self._resolved_path).st_mtime

        except OSError as e:
            # probably a permissions issue; this should be fatal
            logger.id(logger.critical, self,
                    'Failed to stat \'{path}\'',
                    path=self.path,
                    exc_info=True,
            )
            raise
        return db

    def __contains__(self, thing):
        from src import reddit

        name = reddit.subreddit_display_name(thing)
        if not name:
            logger.id(logger.debug, self,
                    'Unhandled __contains__ type for \'{thing}\' ({type})',
                    thing=thing,
                    type=type(thing),
            )
            return

        cursor = self._db.execute(
                'SELECT subreddit_name FROM subreddits'
                ' WHERE subreddit_name = ?',
                (name,),
        )
        return bool(cursor.fetchone())

    @property
    def _create_table_data(self):
        return (
                'subreddits('
                '   subreddit_name TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,'
                '   added_utc REAL NOT NULL'
                ')'
        )

    def _initialize_tables(self, db):
        if self.do_seed:
            logger.id(logger.debug, self,
                    'Seeding subreddits database from \'{path}\' ...',
                    path=SUBREDDITS_DEFAULTS_PATH,
            )

            try:
                with open(SUBREDDITS_DEFAULTS_PATH, 'r') as fd:
                    subreddits = fd.read().split('\n')

            except OSError as e:
                logger.id(logger.warn, self,
                        'Failed to seed subreddits database from'
                        ' \'{path}\'!',
                        path=SUBREDDITS_DEFAULTS_PATH,
                        exc_info=True,
                )

            else:
                subreddits = [
                        name.strip()
                        for name in subreddits if bool(name.strip())
                ]

                logger.id(logger.debug, self,
                        'Seeding with: {color_subreddits}',
                        color_subreddits=subreddits,
                )

                if subreddits:
                    cursor = db.execute('SELECT subreddit_name FROM subreddits')
                    current_subreddits = set(
                            row['subreddit_name'] for row in cursor
                    )
                    to_remove = [
                            name for name in current_subreddits
                            if name not in subreddits
                    ]

                    with db:
                        added = set()
                        for name in subreddits:
                            try:
                                db.execute(
                                        'INSERT INTO'
                                        ' subreddits(subreddit_name, added_utc)'
                                        ' VALUES(?, ?)',
                                        (name, time.time()),
                                )
                            except UniqueConstraintFailed:
                                # just ignore duplicates; probably means we're
                                # trying to seed the database every time in case
                                # the defaults file is updated
                                pass
                            else:
                                added.add(name)

                        if added:
                            logger.id(logger.info, self,
                                    'Added #{num} subreddit{plural}',
                                    num=len(added),
                                    plural=('' if len(added) == 1 else 's'),
                            )
                            logger.id(logger.debug, self,
                                    'Added: {color_names}',
                                    color_names=added,
                            )

                        # remove any subreddits in the database that are missing
                        # from the file
                        if to_remove:
                            logger.id(logger.info, self,
                                    'Removing #{num} missing subreddit{plural}',
                                    num=len(to_remove),
                                    plural=('' if len(to_remove) == 1 else 's'),
                            )
                            logger.id(logger.debug, self,
                                    'Removed: {color_names}',
                                    color_names=to_remove,
                            )

                            db.executemany(
                                    'DELETE FROM subreddits'
                                    ' WHERE subreddit_name = ?',
                                    [(name,) for name in to_remove],
                            )

    def _insert(self, thing):
        from src import reddit

        name = reddit.subreddit_display_name(thing)
        if not name:
            logger.id(logger.debug, self,
                    'Cannot add \'{thing}\' to subreddits database:'
                    ' unhandled type=\'{type}\'',
                    thing=thing,
                    type=type(thing),
            )
            return

        self._db.execute(
                'INSERT INTO subreddits(subreddit_name, added_utc)'
                ' VALUES(?, ?)',
                (name, time.time()),
        )

    def _delete(self, thing):
        from src import reddit

        name = reddit.subreddit_display_name(thing)
        if not name:
            logger.id(logger.debug, self,
                    'Cannot remove \'{thing}\' from subreddits database:'
                    ' unhandled type=\'{type}\'',
                    thing=thing,
                    type=type(thing),
            )

        self._db.execute(
                'DELETE FROM subreddits WHERE subreddit_name = ?',
                (name,)
        )

    @property
    def is_dirty(self):
        return self.__mtime != os.stat(self._resolved_path).st_mtime

    @contextmanager
    def updating(self):
        """
        Update context-manager intended for updating purposes (re-fetching
        new database records into memory).

        eg.
        >>> sd = SubredditsDatabase(...)
        >>> with sd.updating():
        ...     if sd.is_dirty:
        ...         new_data = sd.get_all_subreddits()
        """
        yield
        if self.is_dirty:
            self.__mtime = os.stat(self._resolved_path).st_mtime

    def get_all_subreddits(self):
        cursor = self._db.execute('SELECT subreddit_name FROM subreddits')
        return set(row['subreddit_name'] for row in cursor)

    def get_all_subreddits_added_before(self, timestamp):
        cursor = self._db.execute(
                'SELECT subreddit_name FROM subreddits'
                ' WHERE added_utc < ?',
                (timestamp,),
        )
        return set(row['subreddit_name'] for row in cursor)

    def get_all_subreddits_added_after(self, timestamp):
        cursor = self._db.execute(
                'SELECT subreddit_name FROM subreddits'
                ' WHERE added_utc > ?',
                (timestamp,),
        )
        return set(row['subreddit_name'] for row in cursor)


__all__ = [
        'SubredditsDatabase',
]

