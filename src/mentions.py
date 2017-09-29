from src import (
        config,
        database,
        reddit,
        replies,
)
from src.mixins import (
        ProcessMixin,
        StreamMixin,
)
from src.util import logger


class Mentions(ProcessMixin, StreamMixin):
    """
    Username mentions (in comments) parser
    """

    def __init__(self, cfg, rate_limited, rate_limit_time, blacklist):
        ProcessMixin.__init__(self)
        StreamMixin.__init__(self, cfg, rate_limited, rate_limit_time)

        self.blacklist = blacklist
        self.reply_history = database.ReplyDatabase()
        self.reply_queue = database.ReplyQueueDatabase()
        self.filter = replies.Filter(cfg, self._reddit.username_raw)

    @property
    def _stream_method(self):
        self._reddit.inbox.mentions

    def _process_mention(self, mention):
        """
        Processes the submission the bot was summoned to by the given comment
        """
        submission = mention.submission
        if not submission:
            # this shouldn't happen
            logger.id(logger.debug, self,
                    '{color_mention} has no submission ?!',
                    color_mention=reddit.display_fullname(mention),
            )
            return

        had_replyable_comment = False
        for comment in submission.comments.list():
            ig_usernames = self.filter.replyable_usernames(comment)
            if ig_usernames:
                had_replyable_comment = True
                self.filter.enqueue(comment)

        if not had_replyable_comment:
            # summoned to a thread where the bot attempted no replies
            replied = self.reply_history.replied_comments_for_submission(
                    submission
            )
            if not replied:
                # the bot was summoned to a post with no replyable comments.
                # 1) comment contains 1+ non hyperlinked urls to instagram users
                # 2) comment with links was edited/deleted/removed
                # 3) mention author is trolling the bot
                self.blacklist.increment_bad_actor(mention)

    def _run_forever(self):
        mentions_db = database.MentionsDatabase()
        delay = 15 # too long?

        try:
            while not self._killed.is_set():
                logger.id(logger.debug, self, 'Processing mentions ...')
                for mention in self.stream:
                    if mentions_db.has_seen(mention):
                        # assumption: inbox.mentions fetches newest -> oldest
                        logger.id(logger.debug, self,
                                'I\'ve already processed {color_mention} from'
                                ' {color_from}!',
                                color_mention=reddit.display_fullname(mention),
                                color_from=reddit.author(mention),
                        )
                        break

                    elif self._killed.is_set():
                        logger.id(logger.debug, self, 'Killed!')

                    elif mention is None:
                        break

                    try:
                        with mentions_db:
                            mentions_db.insert(mention)
                    except database.UniqueConstraintFailed:
                        # this means there is a bug in has_seen
                        logger.id(logger.warn, self,
                                'Attempted to process duplicate submission:'
                                ' {color_mention} from {color_from}!',
                                color_mention=reddit.display_fullname(mention),
                                color_from=reddit.author(mention),
                                exc_info=True,
                        )
                        break

                    self._process_mention(mention)

                if not self._killed.is_set():
                    logger.id(logger.debug, self,
                            'Waiting {time} before checking messages again ...',
                            time=delay,
                    )
                self._killed.wait(delay)

        except Exception as e:
            # TODO? only catch praw errors
            logger.id(logger.exception, self,
                    'Something went wrong! Message processing terminated.',
            )


__all__ = [
        'Mentions',
]

