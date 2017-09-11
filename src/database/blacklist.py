import time

from utillib import logger

from ...constants import DEFAULT_BLACKLIST_PATH
from _database import Database


class BlacklistDatabase(Database):
    """
    Storage of blacklisted subreddits/users
    """

    TYPE_SUBREDDIT = '__subreddit__'
    TYPE_USER      = '__user__'

    def __init__(self, path, cfg, do_seed):
        """
        path (str) - path to the database file
        cfg (config.Config) - Config instance
        do_seed (bool) - whether the database should be seeded from the default
                         BLACKLIST file in the root directory of the repo
        """
        Database.__init__(self, path)
        self.cfg = cfg
        self.do_seed = do_seed

    @property
    def _create_table_data(self):
        return (
                'blacklist('
                '   uid INTEGER PRIMARY KEY'
                # case-insensitive
                # https://stackoverflow.com/a/973785
                '   name TEXT NOT NULL COLLATE NOCASE,'
                '   type TEXT NOT NULL CHECK(type IN (\'{0}\')),'
                '   start REAL'
                '   UNIQUE(name, type)'
                ')'.format(
                    # format in the valid type strings: foo','bar','...','baz
                    '\',\''.join([
                        BlacklistDatabase.TYPE_SUBREDDIT,
                        BlacklistDatabase.TYPE_USER,
                    ])
                )
        )

    def _initialize_tables(self, db):
        if self.do_seed:
            logger.prepend_id(logger.debug, self,
                    'Seeding blacklist database from \'{path}\' ...',
                    path=DEFAULT_BLACKLIST_PATH,
            )

            try:
                with open(DEFAULT_BLACKLIST_PATH, 'rb') as fd:
                    # assumption: all lines are subreddits
                    subreddits = fd.read().split('\n')

            except OSError as e:
                logger.prepend_id(logger.error, self,
                        'Failed to seed blacklist database from \'{path}\'!', e,
                        path=DEFAULT_BLACKLIST_PATH,
                )

            else:
                sub_type = BlacklistDatabase.TYPE_SUBREDDIT
                subreddits = [
                    (sub.strip(), sub_type, -1)
                    for sub in subreddits
                    if bool(sub.strip())
                ]
                with db:
                    db.executemany(
                            'INSERT INTO blacklist(name, type, start)'
                            ' VALUES(?, ?, ?)',
                            subreddits,
                    )

    def _insert(self, name, name_type, is_tmp=False):
        """
        name (str) - the name to blacklist
        name_type (str) - should correspond to one of the TYPE_* constants
        is_tmp (bool, optional) - whether the name is a temporary blacklist
        """
        now = time.time() if is_tmp else -1
        with self._db as connection:
            connection.execute(
                    'INSERT INTO blacklist(name, type, start) VALUES(?, ?, ?)',
                    (name, name_type, now),
            )

    def is_blacklisted_subreddit(self, name):
        """
        Returns whether the given subreddit is blacklisted
        """
        cursor = self._db.execute(
                'SELECT start FROM blacklist WHERE name = ? AND type = ?',
                (name, BlacklistDatabase.TYPE_SUBREDDIT),
        )
        # assumption: subreddits cannot be temporarily banned
        return bool(cursor.fetchone())

    def is_blacklisted_user(self, name):
        """
        Returns whether the given user is blacklisted
        """
        cursor = self._db.execute(
                'SELECT start FROM blacklist WHERE name = ? AND type = ?',
                (name, BlacklistDatabase.TYPE_USER),
        )
        row = cursor.fetchone()
        self.__try_prune_temp_ban(row, name, BlacklistDatabase.TYPE_USER)
        return bool(row)

    def __try_prune_temp_ban(self, row, name, name_type):
        """
        Returns float ban time remaining in seconds if still banned
                -1 if ban is permanent
                None if not banned
        """
        if not row:
            return None

        start = row['start']
        if start < 0:
            return start

        elapsed = time.time() - start
        remaining = self.cfg.blacklist_temp_ban_time - elapsed
        if remaining <= 0:
            # blacklist expired
            logger.prepend_id(logger.debug, self,
                    '/u/{user} temp blacklist expired {time} ago:'
                    ' lifting blacklist ...',
                    user=name,
                    time=remaining,
            )
            with self._db as connection:
                connection.execute(
                        'DELETE FROM blacklist WHERE'
                        ' name = ? AND type = ?',
                        (name, name_type),
                )
            remaining = None

        return remaining

    def blacklist_time_left_seconds(self, name):
        """
        Returns the time left in seconds of a temporary blacklist
                -1 if the blacklist is permanent
                None if the name is not blacklisted
        """
        cursor = self._db.execute(
                'SELECT start FROM blacklist WHERE name = ? AND type = ?',
                # assumption: only users can be temporarily blacklisted
                (name, BlacklistDatabase.TYPE_USER),
        )
        row = cursor.fetchone()
        return self.__try_prune_temp_ban(row, name, BlacklistDatabase.TYPE_USER)


__all__ = [
        'BlacklistDatabase',
]

