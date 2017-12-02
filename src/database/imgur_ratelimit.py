import sqlite3
import time

from ._database import Database
from src.config import parse_time


class ImgurRateLimitDatabase(Database):
    """
    Imgur ratelimit handling database
    """

    PATH = 'imgur-ratelimit.db'
    # the number of credits to hold as a buffer since imgur's ratelimit headers
    # don't appear to be 100% accurate
    BUFFER = 1
    # the max age of each respective ratelimit pool
    # XXX: these are hardcoded instead of relying on imgur's response headers
    # because it seems as though (at time of writing) the response headers are
    # one request behind. so the response headers appear to contain ratelimit
    # information for the previous request.
    # ** these may cause the bot to become imgur ratelimited if they ever
    # change the timing of these ratelimit pools.
    CLIENT_MAX_AGE = parse_time('24h')
    USER_MAX_AGE = parse_time('1h')
    POST_MAX_AGE = parse_time('1h')

    @staticmethod
    def parse_headers(response):
        """
        Parses the response for ratelimit headers

        Returns the tuple(
                    client_limit,
                    client_remaining,
                    user_limit,
                    user_remaining,
                    user_reset,
                    post_limit,
                    post_remaining,
                    post_reset,
                ); the respective value will be None if the response headers
                    are missing that specific header (eg. post_limit will be
                    None if the 'X-Post-Rate-Limit-Limit' header is not
                    present)

                or None if the response has no headers
        """
        if not (
                hasattr(response, 'headers')
                and isinstance(response.headers, dict)
        ):
            return None

        def lookup_header(key):
            result = None
            try:
                result = int(response.headers[key])
            except (KeyError, TypeError, ValueError):
                pass
            return result

        return (
                lookup_header('X-RateLimit-ClientLimit'),
                lookup_header('X-RateLimit-ClientRemaining'),
                lookup_header('X-RateLimit-UserLimit'),
                lookup_header('X-RateLimit-UserRemaining'),
                lookup_header('X-RateLimit-UserReset'),
                lookup_header('X-Post-Rate-Limit-Limit'),
                lookup_header('X-Post-Rate-Limit-Remaining'),
                lookup_header('X-Post-Rate-Limit-Reset'),
        )

    def __init__(self, cfg, dry_run=False, *args, **kwargs):
        Database.__init__(self, dry_run=False, *args, **kwargs)
        self.cfg = cfg

    @property
    def _create_table_data(self):
        return (
                # per-day ratelimit
                'client('
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   timestamp REAL NOT NULL,'
                '   limit INTEGER NOT NULL,' # this will probably be constant
                '   remaining INTEGER NOT NULL,'
                '   url TEXT NOT NULL,'
                '   body TEXT' # request data
                ')',

                # per-ip, per-hour ratelimit
                'user('
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   timestamp REAL NOT NULL,'
                '   limit INTEGER NOT NULL,' # this will probably be constant
                '   remaining INTEGER NOT NULL,'
                '   reset INTEGER NOT NULL,'
                '   url TEXT NOT NULL,'
                '   body TEXT' # request data
                ')',

                # per-hour POST ratelimit
                'post('
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   timestamp REAL NOT NULL,'
                '   limit INTEGER NOT NULL,' # this will probably be constant
                '   remaining INTEGER NOT NULL,'
                '   reset INTEGER NOT NULL,'
                '   url TEXT NOT NULL,'
                '   body TEXT' # request data
                ')',
        )

    def __prune(self):
        """
        Prunes the database of expired entries
        """
        def prune(table, max_age):
            expired = time.time() - max_age
            cursor = self._db.execute(
                    'DELETE FROM {0} WHERE timestamp < ?'.format(table),
                    (expired,),
            )
            return cursor.rowcount

        num_deleted_client = prune(
                'client', ImgurRateLimitDatabase.CLIENT_MAX_AGE
        )
        num_deleted_user = prune('user', ImgurRateLimitDatabase.USER_MAX_AGE)
        num_deleted_post = prune('post', ImgurRateLimitDatabase.POST_MAX_AGE)

        if num_deleted_client or num_deleted_user or num_deleted_post:
            msg = ['Pruned from ratelimit pool(s):']
            if num_deleted_client:
                msg.append('#{num_client} client')
            if num_deleted_user:
                msg.append('#{num_user} user')
            if num_deleted_post:
                msg.append('#{num_post} post')
            logger.id(logger.debug, self,
                    ' '.join(msg),
                    num_client=num_deleted_client,
                    num_user=num_deleted_user,
                    num_post=num_deleted_post,
            )
            self._db.commit()

    def _insert(self, response):
        self.__prune()

        data = ImgurRateLimitDatabase.parse_headers(response)
        if data:
            url = response.url
            body = response.request.body

            client_limit, client_remaining = data[0], data[1]
            if client_limit and client_remaining:
                self._db.execute(
                        'INSERT INTO'
                        ' client(timestamp, limit, remaining, url, body)'
                        ' VALUES(?, ?, ?, ?, ?)',
                        (
                            time.time(),
                            client_limit,
                            client_remaining,
                            url,
                            body,
                        ),
                )

            user_limit, user_remaining, user_reset = data[2], data[3], data[4]
            if user_limit and user_remaining and user_reset:
                self._db.execute(
                        'INSERT INTO'
                        ' user(timestamp, limit, remaining, reset, url, body)'
                        ' VALUES(?, ?, ?, ?, ?, ?)',
                        (
                            time.time(),
                            user_limit,
                            user_remaining,
                            user_reset,
                            url,
                            body,
                        ),
                )

            post_limit, post_remaining, post_reset = data[5], data[6], data[7]
            if post_limit and post_remaining and post_reset:
                self._db.execute(
                        'INSERT INTO'
                        ' user(timestamp, limit, remaining, reset, url, body)'
                        ' VALUES(?, ?, ?, ?, ?, ?)',
                        (
                            time.time(),
                            post_limit,
                            post_remaining,
                            post_reset,
                            url,
                            body,
                        ),
                )

    def __get_remaining(self, table):
        """
        Returns the number of requests remaining in the given ratelimit pool
        """
        self.__prune()

        remaining = None
        cursor = self._db.execute(
                'SELECT remaining FROM {0}'
                ' ORDER BY remaining ASC LIMIT 1'.format(table)
        )
        row = cursor.fetchone()
        if row:
            remaining = row['remaining'] - ImgurRateLimitDatabase.BUFFER
            if remaining < 0:
                # too many requests were made; this should hopefully not happen
                actual_remaining = remaining + ImgurRateLimitDatabase.BUFFER
                logger.id(logger.debug, self,
                        '#{remaining} lower than buffer={buf}!',
                        remaining=actual_remaining,
                        buf=ImgurRateLimitDatabase.BUFFER,
                )

        if remaining is None:
            # client table is empty: all credits should be available
            # (ie, not ratelimited)
            remaining = 250 # just return a non-ratelimited value

        return remaining

    def __get_limit(self, table):
        """
        Returns the request limit for the given ratelimit pool
                or -1 if the given pool has no rows
        """
        self.__prune()

        limit = -1
        cursor = self._db.execute(
                'SELECT limit FROM {0}'
                ' ORDER BY limit ASC LIMIT 1'.format(table)
        )
        row = cursor.fetchone()
        if row:
            limit = row['limit']

        return limit

    def __get_time_left(self, table, max_age):
        """
        Returns the time in seconds until the given ratelimit pool is reset
                or 0 if not ratelimited for the given pool
        """
        if self.__get_remaining(table) <= 0:
            return 0

        self.__prune()

        time_left = 0
        # try looking up the imgur ratelimit expire time
        try:
            # TODO: issue: imgur's -*Reset field is based on the most recent
            # request so ORDER BY .. DESC will cause the ratelimit to wait too
            # long (ie, for basically the entire pool to reset before allowing
            # new requests)
            cursor = self._db.execute(
                    'SELECT reset FROM {0}'
                    ' ORDER BY reset DESC LIMIT 1'.format(table)
            )
        except sqlite3.OperationalError:
            # no such column: reset
            pass
        else:
            row = cursor.fetchone()
            if row:
                time_left = row['reset'] - time.time()
                if time_left < 0:
                    # expired row not pruned: either a bug in __prune
                    # or imgur's ratelimit header -*Reset field was incorrect
                    # or imgur changed how long it takes for this ratelimit
                    # pool to reset
                    pass # TODO? log? probably spammy

        cursor = self._db.execute(
                'SELECT timestamp FROM {0} ORDER BY timestamp ASC LIMIT 1'
        )
        row = cursor.fetchone()
        if row:
            elapsed = time.time() - row['timestamp']
            # choose the higher time remaining value to (hopefully) completely
            # avoid hitting imgur's ratelimit
            time_left = max(time_left, max_age - elapsed)

        return time_left

    def get_client_remaining(self):
        """
        Returns the number of requests remaining in the client ratelimit pool
        """
        return self.__get_remaining('client')

    def get_client_limit(self):
        """
        Returns the total number of requests that can be made in the client pool
        """
        return self.__get_limit('client')

    def get_client_time_left(self):
        """
        Returns the time in seconds until the client ratelimit is reset
                or 0 if not ratelimited for the client pool
        """
        return self.__get_time_left(
                'client', ImgurRateLimitDatabase.CLIENT_MAX_AGE
        )

    def get_user_remaining(self):
        """
        Returns the number of requests remaining in the user ratelimit pool
        """
        return self.__get_remaining('user')

    def get_user_limit(self):
        """
        Returns the total number of requests that can be made in the user pool
        """
        return self.__get_limit('user')

    def get_user_time_left(self):
        """
        Returns the time in seconds until the user ratelimit is reset
                or 0 if not ratelimited for the user pool
        """
        return self.__get_time_left('user', ImgurRateLimitDatabase.USER_MAX_AGE)

    def get_post_remaining(self):
        """
        Returns the number of requests remaining in the post ratelimit pool
        """
        return self.__get_remaining('post')

    def get_post_limit(self):
        """
        Returns the total number of requests that can be made in the post pool
        """
        return self.__get_limit('post')

    def get_post_time_left(self):
        """
        Returns the time in seconds until the post ratelimit is reset
                or 0 if not ratelimited for the post pool
        """
        return self.__get_time_left('post', ImgurRateLimitDatabase.POST_MAX_AGE)

    def _get_count(self, table):
        return self._db.execute(
                'SELECT count(*) FROM {0}'.format(table)
        ).fetchone()[0]

    @property
    def num_client(self):
        return self._get_count('client')

    @property
    def num_user(self):
        return self._get_count('user')

    @property
    def num_post(self):
        return self._get_count('post')


__all__ = [
        'ImgurRateLimitDatabase',
]

