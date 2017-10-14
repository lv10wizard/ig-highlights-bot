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

    def __init__(self, cfg, rate_limited, blacklist, dry_run):
        ProcessMixin.__init__(self)
        StreamMixin.__init__(self, cfg, rate_limited)

        self.dry_run = dry_run
        self.blacklist = blacklist
        self.reply_history = database.ReplyDatabase()
        self.reply_queue = database.ReplyQueueDatabase()

    @property
    def _stream_method(self):
        return self._reddit.inbox.mentions

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

        logger.id(logger.info, self,
                'Processing {color_submission}',
                color_submission=reddit.display_id(submission),
        )

        had_replyable_comment = False
        for comment in submission.comments.list():
            ig_usernames = self.filter.replyable_usernames(comment)
            if ig_usernames:
                had_replyable_comment = True
                self.filter.enqueue(comment, ig_usernames, mention)

        # XXX: flagging bad actors from failed mentions temporarily(?) turned
        # off because there are too many false positive cases. further, I doubt
        # trolling through mentions will be that big of an issue since there
        # really is no visible effect for the offending user.

        # if not had_replyable_comment:
        #     # summoned to a thread where the bot attempted no replies
        #     replied = self.reply_history.replied_things_for_submission(
        #             submission
        #     )
        #     if not replied:
        #         # the bot was summoned to a post with no replyable comments.
        #         # - comment has 1+ non hyperlinked urls to instagram users
        #         # - comment with links was edited/deleted/removed
        #         # - subreddit/comment with links is blacklisted
        #         # - mention author is trolling the bot
        #         self.blacklist.increment_bad_actor(mention)

    def _run_forever(self):
        # XXX: instantiated here so that the _reddit instance is constructed
        # in the child process
        self.filter = replies.Filter(
                self.cfg, self._reddit.username_raw, self.blacklist
        )

        mentions_db = database.MentionsDatabase()
        delay = 60 # too long?
        first_run = True

        while not self._killed.is_set():
            logger.id(logger.debug, self, 'Processing mentions ...')
            for mention in self.stream:
                if mention is None or self._killed.is_set():
                    break

                elif mentions_db.has_seen(mention):
                    logger.id(logger.debug, self,
                            'I\'ve already processed {color_mention} from'
                            ' {color_from}!',
                            color_mention=reddit.display_fullname(mention),
                            color_from=reddit.author(mention),
                    )
                    if first_run:
                        continue
                    else:
                        break

                # don't add any mentions to the seen database if this is a dry
                # run since the bot won't be committing any replies
                if not self.dry_run:
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

            first_run = False

            if not self._killed.is_set():
                logger.id(logger.debug, self,
                        'Waiting {time} before checking mentions again ...',
                        time=delay,
                )
            self._killed.wait(delay)

        if self._killed.is_set():
            logger.id(logger.debug, self, 'Killed!')


__all__ = [
        'Mentions',
]

