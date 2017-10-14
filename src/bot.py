import re
import signal
import time

from six import iteritems

from src import (
        blacklist,
        controversial,
        instagram,
        mentions,
        messages,
        ratelimit,
        reddit,
        replies,
        submissions,
)
from src.mixins import (
        RunForeverMixin,
        SubredditsCommentStreamMixin,
)
from src.util import logger


class IgHighlightsBot(RunForeverMixin, SubredditsCommentStreamMixin):
    """
    Instagram Highlights reddit bot class

    This is intended to be run in the main process. It spawns all other
    processes and crawls comments from subreddits in the subreddits database.
    """

    def __init__(self, cfg):
        self._killed = False
        # this is created here so that any process can flag that the account
        # is rate-limited.
        rate_limited = ratelimit.Flag()
        SubredditsCommentStreamMixin.__init__(self, cfg, rate_limited)

        self.blacklist = blacklist.Blacklist(cfg)
        self.ratelimit_handler = ratelimit.RateLimitHandler(
                cfg, rate_limited,
        )
        self.controversial = controversial.Controversial(
                cfg, rate_limited,
        )
        self.submissions = submissions.Submissions(
                cfg, rate_limited, self.blacklist,
        )
        self.messages = messages.Messages(
                cfg, rate_limited, self.blacklist,
        )
        self.mentions = mentions.Mentions(
                cfg, rate_limited, self.blacklist,
        )
        self.replier = replies.Replier(
                cfg, rate_limited, self.blacklist,
        )

        # initialize stuff that requires correct credentials
        instagram.Instagram.initialize(cfg, self._reddit.username)
        self.filter = replies.Filter(
                cfg, self._reddit.username_raw, self.blacklist,
        )

    def __str__(self):
        return self._reddit.username_raw

    def graceful_exit(self, signum=None, frame=None):
        """
        SIGINT/SIGTERM handler

        This will perform an orderly shutdown of the bot and its spawned
        processes.
        """
        # https://stackoverflow.com/a/2549950
        signames = {
                num: name for name, num in
                reversed(sorted(iteritems(signal.__dict__)))
                if name.startswith('SIG') and not name.startswith('SIG_')
        }

        msg = []
        if signum:
            msg.append('Caught {signame} ({num})!')
        msg.append('Shutting down ...')

        try:
            logger.id(logger.debug, self,
                    ' '.join(msg),
                    signame=signames[signum] if signum is not None else '???',
                    num=signum,
            )
        except KeyError as e:
            # signum doesn't match a signal specified in the signal module ...?
            # this is probably not possible
            logger.id(logger.debug, self,
                    ' '.join(msg),
                    signame='???',
                    num=signum,
            )

        self.ratelimit_handler.kill()
        self.controversial.kill()
        self.submissions.kill()
        self.messages.kill()
        self.mentions.kill()
        self.replier.kill()

        self.ratelimit_handler.join()
        self.controversial.join()
        self.submissions.join()
        self.messages.join()
        self.mentions.join()
        self.replier.join()

        # XXX: kill the main process last so that daemon processes aren't
        # killed at inconvenient times
        self._killed = True

    def _run_forever(self):
        """
        Bot comment stream parsing
        """

        # make child processes ignore the signals that the main process handles
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

        self.ratelimit_handler.start()
        self.controversial.start()
        self.submissions.start()
        self.messages.start()
        self.mentions.start()
        self.replier.start()

        # gracefully handle exit signals
        signal.signal(signal.SIGINT, self.graceful_exit)
        signal.signal(signal.SIGTERM, self.graceful_exit)

        while not self._killed:
            # TODO: can GETs cause praw to throw a ratelimit exception?
            for comment in self.stream:
                if not comment or self._killed:
                    break

                logger.id(logger.info, self,
                        'Processing {color_comment}',
                        color_comment=reddit.display_id(comment),
                )

                ig_usernames = self.filter.replyable_usernames(comment)
                if ig_usernames:
                    self.filter.enqueue(comment, ig_usernames)

            if not self._killed:
                time.sleep(1)


__all__ = [
        'IgHighlightsBot',
]

