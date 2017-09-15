from contextlib import contextmanager
import os
import time

from _database import Database

from utillib import logger


class SubredditsDatabase(Database):
    """
    Storage of subreddits to fetch comment streams from
    """

    @staticmethod
    def get_subreddit_name(thing):
        if hasattr(thing, 'subreddit'):
            name = thing.subreddit.display_name
        elif hasattr(thing, 'display_name'):
            name = thing.display_name
        elif isinstance(thing, basestring):
            name = thing
        else:
            name = None
        return name

    def __init__(self, path, do_seed):
        Database.__init__(self, path)
        self.do_seed = do_seed
        try:
            self.__mtime = os.stat(self._resolved_path).st_mtime

        except OSError as e:
            # probably a permissions issue; this should be fatal
            logger.prepend_id(logger.error, self,
                    'Failed to stat \'{path}\'', e, True,
                    path=self.path,
            )

    def __contains__(self, thing):
        name = SubredditsDatabase.get_subreddit_name(thing)
        if not name:
            logger.prepend_id(logger.debug, self,
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

    def _create_table_data(self):
        return (
                'subreddits('
                '   subreddit_name TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,'
                '   added_utc REAL NOT NULL,'
                ')'
        )

    def _initialize_tables(self, db):
        if self.do_seed:
            logger.prepend_id(logger.debug, self,
                    'Seeding subreddits database from \'{path}\' ...',
                    path=SUBREDDITS_DEFAULTS_PATH,
            )

            try:
                with open(SUBREDDITS_DEFAULTS_PATH, 'rb') as fd:
                    subreddits = fd.read().split('\n')

            except OSError as e:
                logger.prepend_id(logger.error, self,
                        'Failed to seed subreddits database from'
                        ' \'{path}\'!', e,
                        path=SUBREDDITS_DEFAULTS_PATH,
                )

            else:
                subreddits = [
                        (name.strip(), time.time())
                        for name in subreddits if bool(name.strip())
                ]
                if subreddits:
                    with db:
                        db.executemany(
                                'INSERT INTO'
                                ' subreddits(subreddit_name, added_utc)'
                                ' VALUES(?, ?)',
                                subreddits,
                        )

    def _insert(self, thing):
        name = SubredditsDatabase.get_subreddit_name(thing)
        if not name:
            logger.prepend_id(logger.debug, self,
                    'Cannot add \'{thing}\' to subreddits database:'
                    ' no \'subreddit\' member!',
                    thing=thing,
            )
            return

        connection.execute(
                'INSERT INTO subreddits(subreddit_name, added_utc)'
                ' VALUES(?, ?)',
                (name, time.time()),
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

