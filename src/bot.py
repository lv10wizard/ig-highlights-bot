import re
import signal
import time

from prawcore.exceptions import Redirect
from six import iteritems

from src import (
        blacklist,
        instagram,
        mentions,
        messages,
        ratelimit,
        reddit,
        replies,
)
from src.database import (
        ReplyQueueDatabase,
        SubredditsDatabase,
)
from src.mixins import (
        RunForeverMixin,
        StreamMixin,
)
from src.util import logger


class IgHighlightsBot(RunForeverMixin, StreamMixin):
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
        StreamMixin.__init__(self, cfg, rate_limited)

        self.ratelimit_handler = ratelimit.RateLimitHandler(cfg, rate_limited)

        self.reply_queue = ReplyQueueDatabase()
        self.subreddits = SubredditsDatabase()
        self.blacklist = blacklist.Blacklist(cfg)

        self.messages = messages.Messages(cfg, rate_limited, self.blacklist)
        self.mentions = mentions.Mentions(cfg, rate_limited, self.blacklist)
        self.replier = replies.Replier(cfg, rate_limited, self.blacklist)

        # initialize stuff that requires correct credentials
        instagram.Instagram.initialize(cfg, self._reddit.username)
        self.filter = replies.Filter(
                cfg, self._reddit.username_raw, self.blacklist
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
        self.messages.kill()
        self.mentions.kill()
        self.replier.kill()

        self.ratelimit_handler.join()
        self.messages.join()
        self.mentions.join()
        self.replier.join()

        # XXX: kill the main process last so that daemon processes aren't
        # killed at inconvenient times
        self._killed = True

    @property
    def _stream(self):
        """
        Cached subreddits.comments stream. This will update the stream generator
        if the subreddits database has been modified.

        Note: renewing the stream will cause some comments to be re-parsed.
        """
        try:
            comment_stream = self.__cached_comment_stream

        except AttributeError:
            comment_stream = None

        if comment_stream is None or self.subreddits.is_dirty:
            with self.subreddits.updating():
                logger.id(logger.info, self, 'Updating subreddits ...')

                try:
                    current_subreddits = self.__current_subreddits

                except AttributeError:
                    current_subreddits = set()

                subs_from_db = self.subreddits.get_all_subreddits()
                # verify that the set of subreddits actually changed
                # (the database file could have been modified with nothing)
                diff = subs_from_db.symmetric_difference(current_subreddits)

                if bool(diff):
                    new = subs_from_db - current_subreddits
                    if new:
                        logger.id(logger.info, self,
                                'New subreddits: {color}',
                                color=new,
                        )
                    removed = current_subreddits - subs_from_db
                    if removed:
                        logger.id(logger.info, self,
                                'Removed subreddits: {color}',
                                color=removed,
                        )

                    subreddits_str = reddit.pack_subreddits(subs_from_db)
                    logger.id(logger.debug, self,
                            'subreddit string:\n{subreddits_str}',
                            subreddits_str=subreddits_str,
                    )
                    if subreddits_str:
                        comment_subreddits = self._reddit.subreddit(
                                subreddits_str
                        )
                        comment_stream = comment_subreddits.stream.comments(
                                pause_after=0
                        )
                        self.__cached_comment_stream = comment_stream
                        self.__current_subreddits = subs_from_db

                else:
                    msg = ['No']
                    if comment_stream is not None:
                        msg.append('new')
                    msg.append('subreddits!')

                    logger.id(logger.info, self, ' '.join(msg))

        return comment_stream

    def _run_forever(self):
        """
        Bot comment stream parsing
        """

        # make child processes ignore the signals that the main process handles
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGTERM, signal.SIG_IGN)

        self.ratelimit_handler.start()
        self.messages.start()
        self.mentions.start()
        self.replier.start()

        # gracefully handle exit signals
        signal.signal(signal.SIGINT, self.graceful_exit)
        signal.signal(signal.SIGTERM, self.graceful_exit)

        try:
            while not self._killed:
                # TODO: can GETs cause praw to throw a ratelimit exception?
                for comment in self.stream:
                    if not comment or self._killed:
                        break

                    logger.id(logger.debug, self,
                            'Processing {color_comment}',
                            color_comment=reddit.display_id(comment),
                    )

                    ig_usernames = self.filter.replyable_usernames(comment)
                    if ig_usernames:
                        self.filter.enqueue(comment, ig_usernames)

                if not self._killed:
                    time.sleep(1)

        except Redirect as e:
            if re.search(r'/subreddits/search', e.message):
                try:
                    subs = self.__current_subreddits
                except AttributeError:
                    # this shouldn't happen
                    logger.id(logger.debug, self,
                            'No current subreddits ...?',
                    )
                    subs = set()

                logger.id(logger.exception, self,
                        'One or more non-existent subreddits: {color}',
                        color=subs,
                )
                raise


__all__ = [
        'IgHighlightsBot',
]

