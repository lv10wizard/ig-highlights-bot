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

    PATH = 'reddit-queue.db'

    __has_elements = multiprocessing.Event()

    @staticmethod
    def fullname(thing):
        try:
            # try subreddit.display_name
            return thing.display_name
        except AttributeError:
            pass

        try:
            # try .fullname
            return thing.fullname
        except AttributeError:
            pass

        # hopefully fullname string
        return thing

    def __contains__(self, thing):
        cursor = self._db.execute(
                'SELECT fullname FROM queue WHERE fullname = ?',
                (RedditRateLimitQueueDatabase.fullname(thing),),
        )
        return bool(cursor.fetchone())

    @property
    def _create_table_data(self):
        return (
                'queue('
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   fullname TEXT NOT NULL,'
                '   submission_fullname TEXT,'
                '   body TEXT,' # comment/submission reply
                '   title TEXT,' # submit title
                '   selftext TEXT,' # submit selftext
                '   url TEXT,' # submit url
                '   ratelimit_reset REAL NOT NULL,'
                '   UNIQUE(fullname, body, title, selftext, url)'
                ')'
        )

    def _insert(
            self, thing, ratelimit_delay, body=None, title=None,
            selftext=None, url=None, submission=None
    ):
        """
        Inserts a thing to reply/post-to to be handled once the bot is no
        longer reddit ratelimited.

        thing (praw.models.*) - the thing to reply or post to
        ratelimit_delay (float) - the amount of time in seconds until the
                ratelimit is over
        body (str, optional) - the body to reply with
        title (str, optional) - the title of the post to submit
        selftext (str, optional) - the selftext of the post to submit
        url (str, optional) - the url of the post to submit
        submission (praw.models.Submission, optional) -
                the submission which contains the thing (if any)

        *Note: body & title/selftext/url are mutually exclusive
        """

        if bool(body) == bool(title or selftext or url):
            # programmer error
            logger.id(logger.warn, self,
                    'Mutually exclusive parameters \'body\''
                    ' & (\'title\' or \'selftext\' or \'url\') both specified!'
                    ' NOT inserting \'{color_thing}\' ...',
                    color_thing=RedditRateLimitQueueDatabase.fullname(thing),
            )
            if body:
                logger.id(logger.debug, self,
                        'body:\n\n{body}\n',
                        body=body,
                )
            if title:
                logger.id(logger.debug, self,
                        'title:\n\n{title}\n',
                        title=title,
                )
            if selftext:
                logger.id(logger.debug, self,
                        'selftext:\n\n{selftext}\n',
                        selftext=selftext,
                )
            if url:
                logger.id(logger.debug, self,
                        'url:\n\n{url}\n',
                        url=url,
                )
            # skip (and lose) data instead of raising an error
            return

        self._db.execute(
                'INSERT INTO'
                ' queue(fullname, submission_fullname, body, title,'
                '       selftext, url, ratelimit_reset)'
                ' VALUES({0})'.format(', '.join(['?'] * 7)),
                (
                    RedditRateLimitQueueDatabase.fullname(thing),
                    RedditRateLimitQueueDatabase.fullname(submission),
                    body,
                    title,
                    selftext,
                    url,
                    time.time() + ratelimit_delay,
                ),
        )
        self.__update_has_elements()

    def _delete(self, thing, body=None, title=None, selftext=None, url=None):
        self._db.execute(
                'DELETE FROM queue WHERE fullname = ?'
                ' AND body = ?'
                ' AND title = ?'
                ' AND selftext = ?'
                ' AND url = ?',
                (
                    RedditRateLimitQueueDatabase.fullname(thing),
                    body,
                    title,
                    selftext,
                    url,
                ),
        )
        self.__update_has_elements()

    def _update(
            self, thing, ratelimit_delay, body=None, title=None,
            selftext=None, url=None,
    ):
        """
        Updates the ratelimit-reset time for the thing
        """
        self._db.execute(
                'UPDATE queue SET ratelimit_reset = ?'
                ' WHERE fullname = ?'
                ' AND body = ?'
                ' AND title = ?'
                ' AND selftext = ?'
                ' AND url = ?',
                (
                    time.time() + ratelimit_delay,
                    RedditRateLimitQueueDatabase.fullname(thing),
                    body,
                    title,
                    selftext,
                    url,
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

    def ig_users_for(self, submission):
        """
        Returns the set of instagram users queued to be posted to thing
                or an empty set if none are found
        """
        from src.replies import Formatter

        try:
            submission.fullname
        except AttributeError:
            # don't accidentally match a random non-submission record
            return set()

        cursor = self._db.execute(
            'SELECT fullname, body FROM queue WHERE submission_fullname = ?',
            (submission.fullname,),
        )

        ig_users = set()
        row = cursor.fetchone()
        if row:
            ig_users = set(Formatter.ig_users_in(row['body']))
            if not ig_users:
                # this probably indicates the reply format changed
                # significantly
                logger.id(logger.debug, self,
                        'No instagram users found in body of \'{color_thing}\''
                        '. body:\n{body}\n\n',
                        color_thing=row['fullname'],
                        body=row['body'],
                )
        return ig_users

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

        Returns tuple (fullname, body, title, selftext, url) of the first
                element where ratelimit_reset is less than the current
                time.time(); ie, the first element that is no longer
                rate-limited. (Note that only body or title/selftext/url will
                have values -- eg. if body has a value then title, selftext and
                url will be None.)

                or None if all elements are still rate-limited and the timeout
                has expired.
        """
        query = 'SELECT * FROM queue ORDER BY ratelimit_reset ASC'
        row = self._db.execute(query).fetchone()
        if not row:
            if block:
                # don't log if a timeout exists to prevent potential log spam
                if timeout is None or timeout < 0:
                    logger.id(logger.debug, self,
                            'Waiting for elements ...'.join(msg),
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
            if delay > 0:

                # prevent ratelimit logging spam
                self.do_log(logger.info,
                        '{color_fullname}: {time} until rate-limit reset',
                        force_=(delay <= 3),
                        color_fullname=row['fullname'],
                        time=delay,
                )

                # still rate-limited
                if block:
                    if timeout is not None and delay > timeout:
                        # prevent possibly flooding the logs when ratelimited
                        self.do_log(logger.debug,
                                'Sleeping timeout={time} ...',
                                time=timeout,
                        )

                        # wait out the rest of the timeout
                        if timeout > 0:
                            time.sleep(timeout)
                        # delay exceeds timeout => still rate-limited
                        row = None

                    else:
                        # wait out the remaining ratelimit time
                        # XXX: don't bother limiting this output since it should
                        # not ever be spammy (I think?)
                        logger.id(logger.debug, self,
                                'Sleeping delay={time} ...',
                                time=delay,
                        )
                        time.sleep(delay)

                else:
                    # still rate-limited but not blocking
                    row = None

        if row:
            return (
                    row['fullname'],
                    row['body'],
                    row['title'],
                    row['selftext'],
                    row['url'],
            )

        return None


__all__ = [
        'RedditRateLimitQueueDatabase',
]

