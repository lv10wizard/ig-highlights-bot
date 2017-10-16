import ctypes
import multiprocessing
import os
import time

import praw.models
from six import integer_types
from six.moves import queue

from src import (
        database,
        replies,
)
from src.config import resolve_path
from src.mixins import (
        ProcessMixin,
        RedditInstanceMixin,
)
from src.util import logger


class Flag(object):
    """
    Persistent, process-safe ratelimited flag which tracks the ratelimit reset
    time
    """

    _PATH = resolve_path(database.Database.PATH_FMT.format('reddit-ratelimit'))

    def __init__(self):
        self.__lock = multiprocessing.RLock()
        self._event = multiprocessing.Event()
        self._value = multiprocessing.Value(ctypes.c_float, 0.0)

        if os.path.exists(Flag._PATH):
            logger.id(logger.info, self,
                    'Loading last ratelimit reset time ...',
            )

            last_reset_time = None
            try:
                with open(Flag._PATH, 'r') as fd:
                    last_reset_time = fd.read()

            except (IOError, OSError):
                logger.id(logger.warn, self,
                        'Failed to read the last ratelimit reset time',
                        exc_info=True,
                )

            else:
                try:
                    last_reset_time = float(last_reset_time)

                except (TypeError, ValueError):
                    logger.id(logger.warn, self,
                            'Invalid ratelimit reset time: \'{val}\' from'
                            ' \'{path}\'',
                            val=last_reset_time,
                            path=Flag._PATH,
                            exc_info=True,
                    )
                    last_reset_time = None

                else:
                    if last_reset_time > time.time():
                        self.value = last_reset_time
                    else:
                        logger.id(logger.info, self,
                                'Last ratelimit reset time expired'
                                ' @ {strftime}!',
                                strftime='%Y/%m/%d %H:%M:%S',
                                strf_time=last_reset_time,
                        )
                        last_reset_time = None

            if last_reset_time is None:
                self._remove_last_reset()

    def __str__(self):
        return self.__class__.__name__

    def _remove_last_reset(self):
        """
        Removes the last ratelimit rest time file
        """
        if os.path.exists(Flag._PATH):
            logger.id(logger.debug, self,
                    'Removing ratelimit reset time file \'{path}\' ...',
                    path=Flag._PATH,
            )

            try:
                os.remove(Flag._PATH)

            except (IOError, OSError):
                logger.id(logger.warn, self,
                        'Failed to remove \'{path}\'!',
                        path=Flag._PATH,
                        exc_info=True,
                )

    @property
    def remaining(self):
        """
        Returns the amount of time remaining until the ratelimit resets
                (0 or negative if not ratelimited)
        """
        return self.value - time.time()

    @property
    def value(self):
        return self._value.value
    @value.setter
    def value(self, reset_time):
        """
        If the reset_time is a positive value > 0, then this will set the
        internal event flag and assign the given value. If the reset_time is
        negative or zero then this will assign the value to 0.0 and clear the
        flag.
        """

        # XXX: I'm not 100% sure locking is necessary. I suppose logging could
        # become a bit confusing if 2+ processes raced in setting the value
        # without it.
        with self.__lock:
            if (
                    isinstance(reset_time, integer_types + (float,))
                    and reset_time > 0
            ):
                self._value.value = reset_time
                self._event.set()

                logger.id(logger.info, self,
                        'Flagging ratelimit: {time} (expires @ {strftime})',
                        time=self.remaining,
                        strftime='%H:%M:%S',
                        strf_time=reset_time,
                )

                try:
                    with open(Flag._PATH, 'w') as fd:
                        fd.write(str(reset_time))

                except (IOError, OSError):
                    logger.id(logger.error, self,
                            'Failed to save ratelimit reset time: \'{val}\''
                            ' ({strftime})!',
                            val=reset_time,
                            strftime='%H:%M:%S',
                            strf_time=reset_time,
                            exc_info=True,
                    )

            else:
                msg = ['Clearing ratelimit:']
                if self.remaining > 0:
                    msg.append('{time} (expires @ {strftime})')
                else:
                    msg.append('expired!')

                logger.id(logger.info, self,
                        ' '.join(msg),
                        time=self.remaining,
                        strftime='%H:%M:%S',
                        strf_time=reset_time,
                )

                self._value.value = 0.0
                self._event.clear()
                self._remove_last_reset()

    def is_set(self):
        return self._event.is_set()

    def wait(self, timeout=None):
        self._event.wait(timeout)

class _RateLimit(ProcessMixin):
    """
    Rate-limit "timer" process
    This handles unsetting the program-wide rate-limited flag.
    """

    def __init__(self, rate_limited):
        ProcessMixin.__init__(self)

        self.rate_limited = rate_limited

    def _run_forever(self):
        while not self._killed.is_set():
            # wait until we've been rate-limited
            # (set a timeout so that killed events can be handled)
            self.rate_limited.wait(1)
            if not self.rate_limited.is_set():
                # timed out
                continue

            # wait until the rate-limit is done
            delay = self.rate_limited.remaining
            if delay > 0:
                logger.id(logger.info, self,
                        'Rate limited! Sleeping {time} ...',
                        time=delay,
                )
                self._killed.wait(delay)

            # don't postpone shutdown to set some variables that are about to
            # be discarded
            if not self._killed.is_set():
                # reset the rate-limit time
                self.rate_limited.value = 0

class RateLimitHandler(ProcessMixin, RedditInstanceMixin):
    """
    Reddit rate-limit handler

    This class handles timing of the rate-limit and queued rate-limited replies
    """

    VALID_THINGS = (
            praw.models.Comment,
            praw.models.Submission,
            praw.models.Message,
    )

    def __init__(self, cfg, rate_limited):
        ProcessMixin.__init__(self)
        RedditInstanceMixin.__init__(self, cfg, rate_limited)

        self.__rate_limit_proc = _RateLimit(rate_limited)

        self.reply_history = database.ReplyDatabase()
        self.rate_limit_queue = database.RedditRateLimitQueueDatabase()

    def kill(self, block=False):
        self.__rate_limit_proc.kill(block)
        ProcessMixin.kill(self, block)

    def join(self):
        self.__rate_limit_proc.join()
        ProcessMixin.join(self)

    def start(self):
        self.__rate_limit_proc.start()
        ProcessMixin.start(self)

    def _run_forever(self):
        from src import reddit

        while not self._killed.is_set():
            handled = False
            try:
                # set a timeout so that kill() calls are registered in a
                # somewhat timely manner
                element = self.rate_limit_queue.get(timeout=1)
            except queue.Empty:
                continue

            if element:
                fullname, body = element

                thing = self._reddit.get_thing_from_fullname(fullname)
                if thing:
                    logger.id(logger.info, self,
                            'Processing {color_thing} ...',
                            color_thing=reddit.display_id(thing),
                    )
                    # only handle specific types of things
                    if isinstance(thing, RateLimitHandler.VALID_THINGS):
                        logger.id(logger.info, self,
                                'Replying to {color_thing} ...',
                                color_thing=reddit.display_id(thing),
                        )

                        # Note: we may be rate-limited again
                        success = self._reddit.do_reply(
                                thing, body, self._killed,
                        )

                        if success or success is None:
                            # reply either succeeded or a reply is not possible
                            # (eg. 403 Forbidden)
                            # remove the element from the queue database
                            with self.rate_limit_queue:
                                self.rate_limit_queue.delete(thing, body)

                        if success:
                            # try to add the thing to the reply history
                            # (but only if we can find instagram users
                            #  in the body)
                            ig_users = replies.Formatter.ig_users_in(
                                    body
                            )
                            if ig_users:
                                try:
                                    with self.reply_history:
                                        self.reply_history.insert(
                                                thing, ig_users,
                                        )

                                except database.UniqueConstraintFailed:
                                    display = reddit.display_id(
                                            thing
                                    )
                                    logger.id(logger.warn, self,
                                            'Duplicate instagram user'
                                            ' posted in'
                                            ' {color_submission}!'
                                            ' (users={color_users})',
                                            color_submission=display,
                                            color_users=ig_users,
                                            exc_info=True,
                                    )
                        handled = True

                if not handled:
                    logger.id(logger.debug, self,
                            'Unhandled body:\n{body}\n\n',
                            body=body,
                    )

                    # remove the element so that it isn't immediately retried
                    logger.id(logger.warn, self,
                            'Removing {color_thing} from queue database ...',
                            color_thing=reddit.display_id(thing),
                    )
                    with self.rate_limit_queue:
                        self.rate_limit_queue.delete(thing, body)

            # else:
            #     # get() timed out, queue not empty
            #     # depending on timeout, this will be spammy
            #     logger.id(logger.debug, self,
            #             'All queue elements are still rate-limited',
            #     )


__all__ = [
        'Flag',
        'RateLimitHandler',
]

