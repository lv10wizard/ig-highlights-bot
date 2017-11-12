import os
import random
import re
import time

from ._database import (
        Database,
        UniqueConstraintFailed,
)
from constants import USER_POOL_PATH


class UserPoolDatabase(Database):
    """
    Pool of instagram usernames for the bot to post to its profile subreddit.

    This database attempts to limit the number of duplicates posted by the bot.
    """

    PATH = 'userpool.db'

    def __init__(self, cfg, *args, **kwargs):
        Database.__init__(self, *args, **kwargs)
        self.cfg = cfg

    def __contains__(self, username):
        cursor = self._db.execute(
                'SELECT username FROM pool WHERE username = ? LIMIT 1',
                (username,),
        )
        row = cursor.fetchone()
        return bool(row and row['username'])

    @property
    def _create_table_data(self):
        return (
                'pool('
                '   username TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,'
                '   last_post_time REAL NOT NULL'
                ')',

                # tracks the last N urls posted for each user
                'last_posts('
                '   uid INTEGER PRIMARY KEY,'
                '   username TEXT NOT NULL COLLATE NOCASE,'
                '   link TEXT NOT NULL COLLATE NOCASE,'
                '   timestamp REAL NOT NULL'
                ')',
        )

    def _insert(self, username):
        self._db.execute(
                'INSERT INTO pool(username, last_post_time)'
                ' VALUES(?, ?)',
                (username, 0.0),
        )

    def _delete(self, username):
        self._db.execute(
                'DELETE FROM pool WHERE username = ?'
                (username,),
        )

    def _update(self, username):
        self._db.execute(
                'UPDATE pool SET last_post_time = ? WHERE username = ?',
                (time.time(), username),
        )

    def __update_from_user_pool_file(self):
        """
        Reads and updates the database with changes from the USER_POOL file
        """
        from src.util import (
                logger,
                readline
        )

        try:
            cached_mtime = self.__pool_file_mtime
        except AttributeError:
            cached_mtime = 0

        current_mtime = os.path.getmtime(USER_POOL_PATH)
        if current_mtime != cached_mtime:
            logger.id(logger.debug, self,
                    'Updating username pool from \'{path}\' ...',
                    path=USER_POOL_PATH,
            )

            seen = set()
            added = set()

            for i, line in readline(USER_POOL_PATH):
                line = line.lower()
                seen.add(line)
                if line not in self:
                    self.insert(line)
                    added.add(line)

            if added:
                logger.id(logger.info, self,
                        'Added #{num} username{plural} to pool: {color}',
                        num=len(added),
                        plural=('' if len(added) == 1 else 's'),
                        color=added,
                )

            # XXX: SELECT in addition to the DELETE query so that the removed
            # usernames can be logged
            cursor = self._db.execute(
                    'SELECT username FROM pool'
                    ' WHERE username NOT IN ({seen})'.format(
                        seen=', '.join(
                            '\'{0}\''.format(name) for name in seen
                        ),
                    )
            )
            removed = set(row['username'] for row in cursor.fetchall())
            if removed:
                self._db.executemany(
                        'DELETE FROM pool WHERE username = ?',
                        [(username,) for username in removed],
                )
                logger.id(logger.info, self,
                        'Removed #{num} username{plural} from pool: {color}',
                        num=len(removed),
                        plural=('' if len(removed) == 1 else 's'),
                        color=removed,
                )

            if added or removed:
                self._db.commit()

    @property
    def last_posts(self, username):
        """
        Returns a list of the most recently posted links for the given user
                sorted from newest -> oldest
        """
        self.__update_from_user_pool_file()
        cursor = self._db.execute(
                'SELECT link FROM last_posts WHERE username = ?'
                ' ORDER BY timestamp DESC'
        )
        return [row['link'] for row in cursor.fetchall()]

    def size(self):
        self.__update_from_user_pool_file()
        cursor = self._db.execute('SELECT count(*) FROM pool')
        return cursor.fetchone()[0]

    def choose_username(self, exclude=[]):
        """
        Chooses a username from the pool that has not been posted recently
        """
        self.__update_from_user_pool_file()
        cursor = self._db.execute(
                'SELECT username FROM pool'
                ' WHERE username NOT IN ({exclude})'
                ' AND ('
                # never posted
                '   last_post_time <= 0'
                # or hasn't been posted recently
                '   OR {now} - last_post_time > {interval}'
                ')'.format(
                    now=time.time(),
                    interval=self.cfg.submit_user_repost_interval,
                    exclude=', '.join(
                        '\'{0}\''.format(name) for name in exclude
                    ),
                )
        )
        return random.choice(cursor.fetchall())['username']

    def commit_post(self, username, link):
        """
        Flags that the given link has been posted for the username
        """
        try:
            self._db.execute(
                    'INSERT INTO last_posts(username, link, timestamp)'
                    ' VALUES(?, ?, ?)',
                    (username, link, time.time()),
            )
        except UniqueConstraintFailed:
            self._db.execute(
                    'UPDATE last_posts'
                    ' SET username = ?, link = ?, timestamp = ?',
                    (username, link, time.time()),
            )

        try:
            self.insert(username)
        except UniqueConstraintFailed:
            pass
        self.update(username)

        # delete the oldest tracked post(s) if the count exceeds the unique
        # links count. this effectively recycles links so that they can be
        # posted again.
        self._db.execute(
                'CASE WHEN ('
                '   SELECT count(link) WHERE username = ?'
                ') > {unique_count}'
                ' THEN'
                '   DELETE FROM last_posts'
                '   WHERE username = ?'
                '   AND timestamp = ('
                '       SELECT timestamp FROM last_posts'
                '       WHERE username = ?'
                '       ORDER BY timestamp LIMIT 1'
                '   )'
                ' END'.format(
                    unique_count=self.cfg.submit_unique_links_per_user,
                ),

                (username, username, username),
        )


__all__ = [
        'UserPoolDatabase',
]

