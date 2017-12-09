import time

from ._database import Database
from src.config import parse_time
from src.util import logger


class GfycatRateLimitDatabase(Database):
    """
    Gfycat ratelimit handling database
    """

    PATH = 'gfycat-ratelimit.db'
    # the time for a request to be re-entered into the ratelimit pool
    MAX_AGE = parse_time('24h')
    # the total number of requests that can be issued within the time window
    LIMIT = 1000

    def __init__(self, cfg, dry_run=False, *args, **kwargs):
        Database.__init__(self, dry_run=False, *args, **kwargs)
        self.cfg = cfg

    @property
    def _create_table_data(self):
        return (
                'ratelimit('
                '   uid INTEGER NOT NULL PRIMARY KEY,'
                '   timestamp REAL NOT NULL,'
                '   url TEXT NOT NULL,'
                '   method TEXT,'
                '   body TEXT'
                ')'
        )

    def __prune(self):
        """
        Prunes expired requests from the database effectivley returning them
        to the ratelimit pool
        """
        expired = time.time() - GfycatRateLimitDatabase.MAX_AGE
        cursor = self._db.execute(
                'DELETE FROM ratelimit WHERE timestamp < ?',
                (expired,),
        )
        if cursor.rowcount > 0:
            logger.id(logger.debug, self,
                    'Pruned #{num} entr{plural}',
                    num=cursor.rowcount,
                    plural=('y' if cursor.rowcount == 1 else 'ies'),
            )
            self._db.commit()

    def _insert(self, response):
        self.__prune()
        if response is not None:
            self._db.execute(
                    'INSERT INTO ratelimit(timestamp, url, method, body)'
                    ' VALUES(?, ?, ?, ?)',
                    (
                        time.time(),
                        response.url,
                        response.request.method,
                        response.request.body,
                    ),
            )

    @property
    def num_used(self):
        """
        Returns the number of requests used
        """
        self.__prune()

        row = self._db.execute('SELECT count(*) FROM ratelimit').fetchone()
        if row:
            # this should always happen
            return row[0]
        return 0

    def get_remaining(self):
        """
        Returns the number of requests remaining in the ratelimit pool
                    ie, the number of requests that can be made before being
                    ratelimited
        """
        self.__prune()
        return GfycatRateLimitDatabase.LIMIT - self.num_used

    def get_time_left(self):
        """
        Returns the time in seconds until no longer ratelimited
                    ie, until at least one request is returned to the ratelimit
                    pool
                or 0 if not currently ratelimited
        """
        self.__prune()

        time_left = 0
        cursor = self._db.execute(
                'SELECT timestamp FROM ratelimit'
                ' ORDER BY timestamp ASC LIMIT 1'
        )
        row = cursor.fetchone()
        if row:
            elapsed = time.time() - row['timestamp']
            time_left = GfycatRateLimitDatabase.MAX_AGE - elapsed
            if time_left < 0:
                # this should not happen (it means there is a bug in __prune)
                logger.id(logger.debug, self,
                        'Failed to calculate time_left'
                        ' (expired row still in database)',
                )
                time_left = 0

        return time_left


__all__ = [
        'GfycatRateLimitDatabase',
]

