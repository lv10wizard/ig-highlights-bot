import time

from ._database import Database
from src.config import parse_time
from src.util import logger


class InstagramRateLimitDatabase(Database):
    """
    Internal instagram rate-limit data
    """

    PATH = Database.PATH_FMT.format('ig-ratelimit.db')

    def __init__(self, max_age):
        Database.__init__(self, InstagramRateLimitDatabase.PATH)
        self.max_age = parse_time(max_age)

    @property
    def _create_table_data(self):
        return (
                'ratelimit('
                # use a meaningless primary key so we never lose any ratelimit
                # hits in the event that two processes attempt to insert at the
                # exact same time
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   timestamp REAL NOT NULL,'
                '   url TEXT NOT NULL COLLATE NOCASE'
                ')'
        )

    def __prune(self):
        """
        Prunes the database of expired entries
        ie,
            now - timestamp > max_age
            now - max_age   > timestamp
        """
        expired = time.time() - self.max_age
        cursor = self._db.execute(
                'DELETE FROM ratelimit WHERE timestamp < ?',
                (expired,),
        )
        if cursor.rowcount > 0:
            logger.id(logger.debug, self,
                    'Pruned #{num} entries ...',
                    num=len(to_prune),
            )
            self._db.commit()

    def _insert(self, url):
        self.__prune()
        # XXX: sqlite proper (not sure about python) will store up to 2^63 - 1
        # integer values.. so I don't think uid int overflow is an issue
        # additionally: https://stackoverflow.com/a/10727574
        #   "If you use INTEGER PRIMARY KEY, it can reuse keys that ...
        #    have been deleted"
        self._db.execute(
                'INSERT INTO ratelimit(timestamp, url) VALUES(?, ?)',
                (time.time(), url),
        )

    def num_used(self):
        """
        Returns the number of requests used (ie, stored in the database)
        """
        self.__prune()
        cursor = self._db.execute('SELECT count(*) FROM ratelimit')
        return cursor.fetchone()[0]

    def time_left(self):
        """
        Returns the time left in seconds until the oldest record in the
        database is pruned
                -1 if the database is empty

                effectively, this returns the time left until at least one
                new request can be made if currently rate-limited
        """
        self.__prune()
        cursor = self._db.execute(
                'SELECT timestamp FROM ratelimit ORDER BY timestamp ASC'
        )

        remaining = -1
        row = cursor.fetchone()
        if row:
            remaining = self.max_age - row['timestamp']

        return remaining


__all__ = [
        'InstagramRateLimitDatabase',
]

