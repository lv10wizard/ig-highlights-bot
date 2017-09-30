import praw.models
from six.moves import queue

from src import (
        database,
        reddit,
        replies,
)
from src.mixins import (
        ProcessMixin,
        RedditInstanceMixin,
)
from src import reddit
from src.util import logger


class _RateLimit(ProcessMixin):
    """
    Rate-limit "timer" process
    This handles unsetting the program-wide rate-limited flag.
    """

    def __init__(self, rate_limited, rate_limit_time):
        ProcessMixin.__init__(self)

        self.rate_limited = rate_limited
        self.rate_limit_time = rate_limit_time

    def _run_forever(self):
        import time

        delay = 1
        while not self._killed.is_set():
            # wait until we've been rate-limited
            # (set a timeout so that killed events can be handled)
            self.rate_limited.wait(delay)
            if not self.rate_limited.is_set():
                # timed out
                continue

            # wait until the rate-limit is done
            delay = time.time() - self.rate_limit_time.value
            logger.id(logger.debug, self,
                    'Rate limited! Sleeping {time} ...',
                    time=delay,
            )
            self._killed.wait(delay)

            # don't postpone shutdown to set some variables that are about to
            # be discarded
            if not self._killed.is_set():
                # reset the rate-limit time
                self.rate_limit_time.value = 0
                # clear the rate-limit flag
                self.rate_limited.clear()

class RateLimitHandler(ProcessMixin, RedditInstanceMixin):
    """
    Reddit rate-limit handler

    This class handles timing of the rate-limit and queued rate-limited replies
    """

    VALID_THINGS = (
            praw.models.Comment,
            praw.models.Message,
    )

    def __init__(self, cfg, rate_limited, rate_limit_time):
        ProcessMixin.__init__(self)
        RedditInstanceMixin.__init__(self, cfg, rate_limited, rate_limit_time)

        self.__rate_limit_proc = _RateLimit(rate_limited, rate_limit_time)

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
                fullname_split = reddit.split_fullname(fullname)
                if isinstance(fullname_split, list):
                    # get the thing name from its prefix
                    type_prefix, thing_id = fullname_split
                    try:
                        thing_name = self._reddit._kinds[type_prefix]
                    except KeyError:
                        logger.id(logger.warn, self,
                                'Unrecognized thing type: \'{type}\'',
                                type=type_prefix,
                                exc_info=True,
                        )

                    else:
                        thing = None

                        # get the thing object
                        if hasattr(self._reddit, thing_name):
                            # comment, submission, subreddit, redditor
                            thing_class = getattr(self._reddit, thing_name)
                            thing = thing_class(thing_id)

                        elif hasattr(praw.models, thing_name.capitalize()):
                            # message
                            # Note: this object is woefully incomplete; eg. it
                            # does not have 'body' or 'author', etc
                            thing_class = getattr(
                                    praw.models,
                                    thing_name.capitalize()
                            )
                            thing = thing_class(self._reddit, None)
                            thing.id = thing_id

                        if thing:
                            logger.id(logger.debug, self,
                                    'Processing {color_thing} ...',
                                    color_thing=reddit.display_fullname(thing),
                            )
                            # only handle specific types of things
                            if isinstance(thing, RateLimitHandler.VALID_THINGS):
                                # Note: we may be rate-limited again
                                if self._reddit.do_reply(thing, body):
                                    # remove the element from the queue database
                                    with self.rate_limit_queue:
                                        self.rate_limit_queue.delete(
                                                thing, body
                                        )

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
                                            display = reddit.display_fullname(
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

                            else:
                                logger.id(logger.debug, self,
                                        'Skipping {color_thing}:'
                                        ' invalid type={type}',
                                        color_thing=reddit.display_fullname(
                                            thing
                                        ),
                                        type=type(thing),
                                )

                        else:
                            logger.id(logger.debug, self,
                                    'Failed to construct \'{thing_name}\''
                                    ' object!',
                                    thing_name=thing_name,
                            )

                else:
                    # random thing inserted into queue
                    logger.id(logger.debug, self,
                            'Unrecognized fullname: \'{fullname}\'',
                            fullname=fullname,
                    )

                if not handled:
                    logger.id(logger.debug, self,
                            'Unhandled body:\n{body}\n\n',
                            body=body,
                    )

                    # remove the element so that it isn't immediately retried
                    logger.id(logger.warn, self,
                            'Removing {color_thing} from queue database ...',
                            color_thing=reddit.display_fullname(thing),
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
        'RateLimitHandler',
]

