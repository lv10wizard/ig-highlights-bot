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
from src.util import (
        logger,
        readline,
)


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
            for i, line in readline(Flag._PATH):
                try:
                    last_reset_time = float(line)

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

                finally:
                    break

            if last_reset_time is None:
                self._remove_last_reset()

    def __str__(self):
        return ':'.join([
            __name__,
            self.__class__.__name__,
        ])

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

    def wait_out_ratelimit(self, event=None):
        """
        Waits the remaining ratelimit time, if any.

        event ({threading,multiprocessing}.Event, optional) -
                The object to use to wait out the remaining time (with the
                object's .wait attribute). If this is not specified, waiting
                will take place with time.sleep (meaning processes will
                become unresponsive during the wait period).
                    Default: None => waits with time.sleep
        """
        delay = self.remaining
        if delay > 0:
            if not (event or hasattr(event, 'wait')):
                logger.id(logger.debug, self,
                        'No \'wait\' method found for event=\'{event}\'!'
                        ' Using time.sleep ...',
                        event=event,
                )
                do_wait = time.sleep
            else:
                do_wait = event.wait

            logger.id(logger.info, self,
                    'Rate limited! Waiting {time} (expires @ {strftime}) ...',
                    time=delay,
                    strftime='%H:%M:%S',
                    strf_time=self.value,
            )
            do_wait(delay)

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
            self.rate_limited.wait_out_ratelimit(self._killed)

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

        self.rate_limited = rate_limited
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

    def _handle_pm(self, to, subject, body):
        """
        Handles a reddit ratelimit queued private massage

        Returns True if the pm was attempted
        """
        logger.id(logger.info, self,
                'Sending pm \'{subject}\' to {color_to} ...',
                subject=subject,
                color_to=to,
        )

        success = self._reddit.do_send_pm(to, subject, body, self._killed)
        if success or success is None:
            logger.id(logger.debug, self,
                    'Removing \'{color_to}\': \'{subject}\' from'
                    ' reddit ratelimit queue ...',
                    color_to=to,
                    subject=subject,
            )
            # pm succeeded or could not be sent
            # remove the element from the queue database
            with self.rate_limit_queue:
                self.rate_limit_queue.delete(
                        thing=to,
                        body=body,
                        title=subject,
                )

        return True # XXX: always handled at the moment

    def _handle_reply(self, fullname, body):
        """
        Handles a reddit ratelimit queued reply

        Returns True if a reply was attempted for the thing
        """
        handled = False
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
                    logger.id(logger.debug, self,
                            'Removing \'{color_thing}\' from'
                            ' reddit ratelimit queue ...',
                            color_thing=thing,
                    )
                    # reply either succeeded or a reply is not possible
                    # (eg. 403 Forbidden)
                    # remove the element from the queue database
                    with self.rate_limit_queue:
                        self.rate_limit_queue.delete(thing, body=body)

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

        return handled

    def _handle_submit(self, display_name, title, selftext, url):
        """
        Handles a reddit ratelimit queued submit

        Returns True if a submit was attempted
        """
        logger.id(logger.info, self,
                'Posting \'{title}\' to {subname} ...',
                title=title,
                subname=display_name,
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

        success = self._reddit.do_submit(
                display_name=display_name,
                title=title,
                selftext=selftext,
                url=url,
                killed=self._killed,
        )

        if success or success is None:
            logger.id(logger.debug, self,
                    'Removing \'{color_thing}\': \'{title}\' from'
                    ' reddit ratelimit queue ...',
                    color_thing=display_name,
                    title=title,
            )
            # submit succeeded or could not be made
            # remove the element from the queue database
            with self.rate_limit_queue:
                self.rate_limit_queue.delete(
                        thing=display_name,
                        title=title,
                        selftext=selftext,
                        url=url,
                )

        # XXX: there is currently no case where the queued item is not handled
        return True

    def _log_element(self, element, msg_prefix=''):
        if logger.is_enabled_for(logger.DEBUG):
            _, body, title, selftext, url = element

            if body:
                logger.id(logger.debug, self,
                        '{prefix}body:\n\n{body}\n',
                        prefix=msg_prefix,
                        body=body,
                )
            if title:
                logger.id(logger.debug, self,
                        '{prefix}title:\n\n{title}\n',
                        prefix=msg_prefix,
                        title=title,
                )
            if selftext:
                logger.id(logger.debug, self,
                        '{prefix}selftext:\n\n{selftext}\n',
                        prefix=msg_prefix,
                        selftext=selftext,
                )
            if url:
                logger.id(logger.debug, self,
                        '{prefix}url:\n\n{url}\n',
                        prefix=msg_prefix,
                        url=url,
                )

    def _run_forever(self):
        from src import reddit

        while not self._killed.is_set():
            handled = False

            self.rate_limited.wait_out_ratelimit(self._killed)
            if self._killed.is_set():
                break

            try:
                # set a timeout so that kill() calls are registered in a
                # somewhat timely manner
                element = self.rate_limit_queue.get(timeout=1)
            except queue.Empty:
                continue

            if element:
                fullname, body, title, selftext, url = element

                # XXX: a bit hacky - determine what we're doing with the
                # ratelimited thing based on the columns that were queued
                if body and title:
                    # pm to redditor
                    handled = self._handle_pm(fullname, title, body)

                elif body:
                    handled = self._handle_reply(fullname, body)

                elif title:
                    handled = self._handle_submit(
                            fullname, title, selftext, url
                    )

                if not handled:
                    self._log_element(element, msg_prefix='Unhandled ')

                    # remove the element so that it isn't immediately retried
                    logger.id(logger.warn, self,
                            'Removing {color_thing} from queue database ...',
                            color_thing=reddit.display_id(thing),
                    )
                    with self.rate_limit_queue:
                        self.rate_limit_queue.delete(
                                thing=thing,
                                body=body,
                                title=title,
                                selftext=selftext,
                                url=url,
                        )

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

