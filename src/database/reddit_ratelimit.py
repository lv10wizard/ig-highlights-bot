import multiprocessing
import time

from six.moves import queue

from ._database import Database
from src.util import logger


class RedditRateLimitQueueDatabase(Database):
    """
    Queue-like database storing rate-limited replies.
    This class aims to be process-safe but I'm not sure it is in all cases.
    """

    __has_elements = multiprocessing.Event()

    @staticmethod
    def fullname(thing):
        try:
            return thing.fullname
        except AttributeError:
            # probably fullname string
            return thing

    def __contains__(self, thing):
        cursor = self._db.execute(
                'SELECT fullname FROM queue WHERE fullname = ?',
                (thing.fullname,),
        )
        return bool(cursor.fetchone())

    def _create_table_data(self):
        return (
                'queue('
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   fullname TEXT NOT NULL COLLATE NOCASE,'
                '   body TEXT NOT NULL,'
                '   ratelimit_reset REAL NOT NULL'
                ')'
        )

    def _insert(self, thing, body, ratelimit_delay):
        self._db.execute(
                'INSERT INTO queue(fullname, body, ratelimit_reset)'
                ' VALUES(?, ?, ?)',
                (
                    RedditRateLimitQueueDatabase.fullname(thing),
                    body,
                    time.time() + ratelimit_delay,
                ),
        )
        self.__update_has_elements()

    def _delete(self, thing, body):
        self._db.execute(
                'DELETE FROM queue WHERE fullname = ? AND body = ?',
                (
                    RedditRateLimitQueueDatabase.fullname(thing),
                    body,
                ),
        )
        self.__update_has_elements()

    def _update(self, thing, body, ratelimit_delay):
        """
        Updates the ratelimit-reset time for the thing
        """
        self._db.execute(
                'UPDATE queue SET ratelimit_reset = ?'
                ' WHERE fullname = ? AND body = ?',
                (
                    time.time() + ratelimit_delay,
                    RedditRateLimitQueueDatabase.fullname(thing),
                    body,
                ),
        )

    def __update_has_elements(self):
        cursor = self._db.execute('SELECT fullname FROM queue')
        if bool(cursor.fetchone()):
            if not RedditRateLimitQueueDatabase.__has_elements.is_set():
                logger.id(logger.debug, self, 'queue has elements')
            RedditRateLimitQueueDatabase.__has_elements.set()
        else:
            if RedditRateLimitQueueDatabase.__has_elements.is_set():
                logger.id(logger.debug, self, 'queue is empty')
            RedditRateLimitQueueDatabase.__has_elements.clear()

    def size(self):
        """
        Returns the current number of elements in the database
        """
        # https://stackoverflow.com/a/669096
        cursor = self._db.execute('SELECT count(*) FROM queue')
        return cursor.fetchone()[0]

    def get(self, block=True, timeout=None):
        """
        Queue-like get

        This will remove the "first" element from the database and return it.
        The first element is the row with the lowest {ratelimit_reset} time.

        Note: this function DOES NOT remove the element from the database
        (this is done to prevent data loss in case the program terminates
         before the element has been fully processed)

        block (bool, optional) - blocks until the queue has an element to return
        timeout (float, optional) - if block is True, will block at most
                {timeout} seconds. if block is False, timeout is ignored.

            queue.Empty is raised if either block == False or timeout is a
            positive number if no item was available.

        Returns (fullname, body) of the first element where ratelimit_reset is
                less than the current time.time(); ie, the first element that
                is no longer rate-limited.

                or None if all elements are still rate-limited and the timeout
                has expired.
        """
        query = 'SELECT * FROM queue ORDER BY ratelimit_reset ASC'
        row = self._db.execute(query).fetchone()
        if not row:
            if block:
                msg = ['Waiting for elements']
                if timeout and timeout > 0:
                    msg.append('(timeout={time})')
                msg.append('...')
                logger.id(logger.debug, self,
                        ' '.join(msg),
                        time=timeout,
                )

                start = time.time()
                RedditRateLimitQueueDatabase.__has_elements.wait(timeout)
                elapsed = time.time() - start
                # adjust the timeout if necessary (in case timeout was woken up
                # because of new elements)
                if timeout:
                    timeout -= elapsed

                row = self._db.execute(query).fetchone()

            if not row:
                raise queue.Empty

        if row:
            delay = row['ratelimit_reset'] - time.time()
            logger.id(logger.debug, self,
                    '{color_fullname}: {time} until rate-limit reset',
                    color_fullname=row['fullname'],
                    time=delay,
            )

            if delay > 0:
                # still rate-limited
                if block:
                    if timeout is not None and delay > timeout:
                        # wait out the rest of the timeout
                        logger.id(logger.debug, self,
                                'Sleeping timeout={time} ...',
                                time=timeout,
                        )
                        if timeout > 0:
                            time.sleep(timeout)
                        # delay exceeds timeout => still rate-limited
                        row = None

                    else:
                        # wait out the remaining ratelimit time
                        logger.id(logger.debug, self,
                                'Sleeping delay={time} ...',
                                time=delay,
                        )
                        time.sleep(delay)

                else:
                    # still rate-limited but not blocking
                    row = None

        return (row['fullname'], row['body']) if row else None


__all__ = [
        'RedditRateLimitQueueDatabase',
]

