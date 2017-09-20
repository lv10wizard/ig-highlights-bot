import re
import time

from ._database import Database
from constants import (
        BLACKLIST_DEFAULTS_PATH,
        PREFIX_USER,
)
from src import reddit
from src.util import logger


class BlacklistDatabase(Database):
    """
    Storage of blacklisted subreddits/users
    """

    PERMANENT = -1

    # XXX: use arbitrary type strings in case reddit's 'u/', 'r/' prefixes
    # change or in case I ever want to add some arbitrary type
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
                '   start REAL,'
                # flag indicating that a temporary ban should be made permanent
                # when it expires
                # -- this exists to prevent users from side-stepping temporary
                # bans by requesting a permanent ban then requesting an unban
                # (the chance that this happens are probably close to zero but
                #  it could in theory happen with how blacklisting is handled
                #  at the moment)
                # XXX: there is no check that the record is temporary (ie, that
                # start is not None) at this level.
                '   make_permanent INTEGER DEFAULT 0,'
                # TODO? blacklist trigger
                #   (eg. comment.fullname, message.fullname, etc)
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
            logger.id(logger.debug, self,
                    'Seeding blacklist database from \'{path}\' ...',
                    path=BLACKLIST_DEFAULTS_PATH,
            )

            try:
                with open(BLACKLIST_DEFAULTS_PATH, 'rb') as fd:
                    # assumption: all lines are subreddits
                    subreddits = fd.read().split('\n')

            except OSError as e:
                logger.id(logger.exception, self,
                        'Failed to seed blacklist database from \'{path}\'!',
                        path=BLACKLIST_DEFAULTS_PATH,
                        exc_info=e,
                )

            else:
                sub_type = BlacklistDatabase.TYPE_SUBREDDIT
                subreddits = [
                    (
                        self.__sanitize(sub, sub_type),
                        sub_type,
                        BlacklistDatabase.PERMANENT,
                    )
                    for sub in subreddits
                    if bool(sub.strip())
                ]
                if subreddits:
                    with db:
                        db.executemany(
                                'INSERT INTO blacklist(name, type, start)'
                                ' VALUES(?, ?, ?)',
                                subreddits,
                        )

    def __sanitize(self, name, name_type):
        # coerce user profile "subreddits" to their display name
        # eg. 'u/foobar' -> 'u_foobar'
        # https://reddit.com/6cfu55
        if name_type == BlacklistDatabase.TYPE_SUBREDDIT:
            return re.sub(r'^/?{0}'.format(PREFIX_USER), 'u_', name.strip())
        return name # TODO? do names need sanitization?

    def _insert(self, name, name_type, is_tmp=False):
        """
        name (str) - the name to blacklist
        name_type (str) - should correspond to one of the TYPE_* constants
        is_tmp (bool, optional) - whether the name is a temporary blacklist
        """
        now = time.time() if is_tmp else BlacklistDatabase.PERMANENT
        name = self.__sanitize(name, name_type)
        connection.execute(
                'INSERT INTO blacklist(name, type, start) VALUES(?, ?, ?)',
                (name, name_type, now),
        )

    def _delete(self, name, name_type):
        name = self.__sanitize(name, name_type)
        connection.execute(
                'DELETE FROM blacklist WHERE name = ? AND type = ?',
                (name, name_type),
        )

    def set_make_permanent(self, name, name_type, value=True):
        flag = 1 if value else 0
        connection.execute(
                'UPDATE blacklist'
                ' SET make_permanent = ?'
                ' WHERE name = ? AND type = ?',
                (flag, name, name_type),
        )

    def clear_make_permanent(self, name, name_type):
        connection.execute(
                'UPDATE blacklist'
                ' SET make_permanent = ?'
                ' WHERE name = ? AND type = ?',
                (0, name, name_type),
        )

    def is_blacklisted(self, name, name_type):
        """
        Returns whether the given name is blacklisted
        """
        if name_type == BlacklistDatabase.TYPE_SUBREDDIT:
            return self.is_blacklisted_subreddit(name)

        elif name_type == BlacklistDatabase.TYPE_USER:
            return self.is_blacklisted_user(name)

        logger.id(logger.debug, self,
                'Unrecognized name_type: \'{type}\'',
                type=name_type,
        )
        return False

    def is_blacklisted_subreddit(self, name):
        """
        Returns whether the given subreddit is blacklisted
        """
        name = self.__sanitize(name, BlacklistDatabase.TYPE_SUBREDDIT)
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

    def is_blacklisted_temporarily(self, name):
        """
        Returns whether the given username is temporarily blacklisted
        """
        cursor = self._db.execute(
                'SELECT start FROM blacklist WHERE name = ? AND type = ?',
                (name, BlacklistDatabase.TYPE_USER),
        )
        row = cursor.fetchone()
        remaining = self.__try_prune_temp_ban(
                row, name, BlacklistDatabase.TYPE_USER
        )
        return (
                remaining > 0
                if isinstance(remaining, (int, float, long))
                else False
        )

    def is_flagged_to_be_made_permanent(self, name):
        """
        Returns whether the given username is flagged to be made permanent when
        their temporary ban expires
        """
        cursor = self._db.execute(
                'SELECT make_permanent FROM blacklist'
                ' WHERE name = ? AND type = ?',
                (name, BlacklistDatabase.TYPE_USER),
        )
        return bool(cursor.fetchone())

    def __try_prune_temp_ban(self, row, name, name_type):
        """
        Returns float ban time remaining in seconds if still banned
                -1 if ban is permanent
                0 if not banned
        """
        if not row:
            return 0

        start = row['start']
        if start < 0:
            return start

        elapsed = time.time() - start
        remaining = self.cfg.blacklist_temp_ban_time - elapsed
        if remaining <= 0:
            # blacklist expired
            name = self.__sanitize(name, name_type)
            make_permanent = self.is_flagged_to_be_made_permanent(name)
            if make_permanent:
                action = 'making permanent'
            else:
                action = 'lifting blacklist'

            logger.id(logger.debug, self,
                    '{user} temp blacklist expired {time} ago:'
                    ' {action} ...',
                    user=reddit.prefix_user(name),
                    time=remaining,
                    action=action,
            )
            with self._db as connection:
                if make_permanent:
                    connection.execute(
                            'UPDATE blacklist'
                            ' SET start = ?, make_permanent = ?'
                            ' WHERE name = ? AND type = ?',
                            (
                                BlacklistDatabase.PERMANENT,
                                0,
                                name,
                                name_type,
                            ),
                    )

                else:
                    connection.execute(
                            'DELETE FROM blacklist WHERE'
                            ' name = ? AND type = ?',
                            (name, name_type),
                    )
            remaining = 0

        return remaining

    def blacklist_time_left_seconds(self, name):
        """
        Returns the time left in seconds of a temporary blacklist
                -1 if the blacklist is permanent
                0 if the name is not blacklisted
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

