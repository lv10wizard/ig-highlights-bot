from .filter import Filter
from .formatter import Formatter
from constants import PREFIX_USER
from src import reddit
from src.database import (
        PotentialSubredditsDatabase,
        ReplyDatabase,
        ReplyQueueDatabase,
        SubredditsDatabase,
        UniqueConstraintFailed,
)
from src.instagram import Instagram
from src.mixins import (
        ProcessMixin,
        RedditInstanceMixin,
)
from src.util import logger


class Replier(ProcessMixin, RedditInstanceMixin):
    """
    Reply queue consumer

    This process does the actual replying for the bot. This is done in a
    separate process so that stream fetching processes are never interrupted.
    """

    def __init__(self, cfg, rate_limited, blacklist, dry_run):
        ProcessMixin.__init__(self)
        RedditInstanceMixin.__init__(self, cfg, rate_limited)

        self.dry_run = dry_run
        self.blacklist = blacklist
        self.subreddits = SubredditsDatabase()
        self.potential_subreddits = PotentialSubredditsDatabase()
        self.reply_history = ReplyDatabase()
        self.reply_queue = ReplyQueueDatabase()

    def _get_instagram_data(self, comment):
        """
        Returns a list of instagram data for each user linked-to by the comment
                or None if there were no reply-able instagram usernames found
                    in the comment (this may happen if the program was
                    terminated before it was able to remove the comment from
                    the queue database or if the comment was deleted)
        """
        # this is (most likely) an extra network hit.
        # it only needs to occur if queue processing was interrupted
        # previously by eg. program termination.
        # (this is also duplicated work but it ensures that comments are
        #  replied-to properly; ie, all instagram users linked to by the
        #  comment are responded to)
        ig_usernames = self.filter.replyable_usernames(
                comment,
                # don't bother with preliminary checks; they should have
                # already passed
                prelim_check=False,
                # no need to check the comment thread for too many bot
                # replies because it should have already been checked
                check_thread=False,
        )

        if not ig_usernames:
            logger.id(logger.debug, self,
                    'No reply-able instagram usernames found in'
                    ' {color_comment}!',
                    color_comment=reddit.display_id(comment),
            )
            return None

        ig_list = []
        for ig_user in ig_usernames:
            ig = Instagram(ig_user, self._killed)
            if ig.top_media:
                ig_list.append(ig)
            else:
                # insert the return of top_media so we can handle appropriately
                ig_list.append(ig.top_media)

            # XXX: 404-based bad actor flagging is turned off (temporarily?)
            # because the bot now tries to match '@username' strings if no links
            # to instagram user pages are found.

            # if 404 in ig.status_codes:
            #     # linked to a non-existent user; probably a typo but the
            #     # user could be trying to troll
            #     self.blacklist.increment_bad_actor(comment)

        return ig_list

    def _add_potential_subreddit(self, submission):
        """
        Adds a new (or increments an existing) potential subreddit to add to the
        bot's default set of crawled subreddits so that it no longer needs to be
        summoned to reply to comments in this subreddit.
        """
        to_add_count = self.potential_subreddits.count(submission)
        threshold = self.cfg.add_subreddit_threshold

        prefixed_subreddit = reddit.prefix_subreddit(
                submission.subreddit.display_name
        )
        if to_add_count <= threshold:
            # not enough to-add points; add to/increment potential subreddits
            logger.id(logger.debug, self,
                    'Adding {color_subreddit} as potential subreddit'
                    ' (#{count})',
                    color_subreddit=prefixed_subreddit,
                    count=to_add_count,
            )

            try:
                with self.potential_subreddits:
                    self.potential_subreddits.insert(submission)
            except UniqueConstraintFailed:
                # this shouldn't happen
                logger.id(logger.warn, self,
                        'Attempted to add/increment duplicate {color_subreddit}'
                        ' to {color_db}',
                        color_subreddit=prefixed_subreddit,
                        color_db=self.potential_subreddits,
                        exc_info=True,
                )
            else:
                to_add_count = self.potential_subreddits.count(submission)

        # check if the count has passed the threshold in case it just changed
        if to_add_count > threshold:
            # add the subreddit as a permanent subreddit that the bot crawls
            logger.id(logger.debug, self,
                    'Adding {color_subreddit} to permanent subreddits',
                    color_subreddit=prefixed_subreddit,
            )

            # add the subreddit to the set
            try:
                with self.subreddits:
                    self.subreddits.insert(submission)
            except UniqueConstraintFailed:
                # this should only happen if this method is called
                # inappropriately
                logger.id(logger.warn, self,
                        'Attmepted to add duplicate subreddit to permanent'
                        ' set of subreddits ({color_subreddit})!',
                        color_subreddit=prefixed_subreddit,
                        exc_info=True,
                )

            # remove the subreddit's to-add count
            with self.potential_subreddits:
                self.potential_subreddits.delete(submission)

    def _reply(self, comment, ig_list):
        """
        Replies to a single comment with (potentially) multiple instagram user
        highlights

        Returns True if successfully replied one or more times
        """
        success = False

        logger.id(logger.info, self,
                'Replying to {color_comment}: {color_list}',
                color_comment=reddit.display_id(comment),
                color_list=ig_list,
        )

        reply_list = self.formatter.format(ig_list)
        if len(reply_list) > self.cfg.max_replies_per_comment:
            # too many replies formed
            logger.id(logger.info, self,
                    '{color_comment} (by {color_author}) almost made me reply'
                    ' #{num} times: skipping.',
                    color_comment=reddit.display_id(comment),
                    color_author=reddit.author(comment),
                    num=len(reply_list),
            )
            # TODO? temporarily blacklist user? (may be trying to break bot)
            # -- could also just be a comment with a lot (like a lot) of
            # instagram user links.
            return

        logger.id(logger.info, self,
                'Replying #{num} time{plural} to {color_comment} ...',
                num=len(reply_list),
                plural=('' if len(reply_list) == 1 else 's'),
                color_comment=reddit.display_id(comment),
        )

        lengths = [len(body) for body, _ in reply_list]
        logger.id(logger.debug, self,
                'Length of repl{plural}: {lengths}',
                plural=('y' if len(lengths) == 1 else 'ies'),
                lengths=lengths,
        )

        if self.dry_run:
            logger.id(logger.info, self,
                    'Dry run: skipping repl{plural} to {color_comment}',
                    plural=('y' if len(reply_list) == 1 else 'ies'),
                    color_comment=reddit.display_id(comment),
            )
            return

        for body, ig_usernames in reply_list:
            if self._reddit.do_reply(comment, body, self._killed):
                # only require a single reply to succeed to consider this method
                # a success
                success = True
                try:
                    self.reply_history.insert(comment, ig_usernames)
                except UniqueConstraintFailed:
                    # this probably means that there is a bug in filter
                    logger.id(logger.warn, self,
                            'Duplicate instagram user posted in'
                            ' {color_submission}! (users={color_users})',
                            color_submission=reddit.display_fullname(
                                comment.submission
                            ),
                            color_user=ig_usernames,
                            exc_info=True,
                    )

        if success:
            self.reply_history.commit()
        return success

    def _process_reply_queue(self):
        """
        Processes the reply-queue until all elements have been seen.
        """

        seen = set()
        while not self._killed.is_set() and self.reply_queue.size() > 0:
            data = self.reply_queue.get()
            if not data:
                # queue is empty
                break

            comment_id, mention_id = data
            if comment_id in seen:
                # all elements in the queue were processed
                break

            seen.add(comment_id)
            comment = self._reddit.comment(comment_id)
            mention = None
            if mention_id:
                mention = self._reddit.comment(mention_id)

            ig_list = self._get_instagram_data(comment)

            if ig_list is None:
                # comment was probably deleted.
                logger.id(logger.debug, self,
                        'No instagram users found in \'{color_comment}!'
                        ' Removing from reply-queue ...',
                        color_comment=reddit.display_id(comment),
                )
                with self.reply_queue:
                    self.reply_queue.delete(comment)

            elif ig_list:
                if None in ig_list:
                    # at least one user's fetch was interrupted.
                    # the comment was queued: cycle it to the back of the queue
                    # so we can check if we can reply immediately to other
                    # comments.
                    with self.reply_queue:
                        self.reply_queue.update(comment)

                else:
                    # remove the comment from the reply-queue if no instagram
                    # users were queued since there should be no further need
                    # to process it.
                    with self.reply_queue:
                        self.reply_queue.delete(comment)

                    orig_list = ig_list
                    ig_list = list(filter(None, ig_list))
                    if len(orig_list) != len(ig_list):
                        # there were some private/non-user pages linked in the
                        # comment
                        if not ig_list:
                            # no user links to post
                            return

                        missing = set(orig_list) - set(ig_list)
                        logger.id(logger.info, self,
                                'Skipping replies for the following users:'
                                '\n{color_missing}',
                                color_missing=missing,
                        )

                    if mention:
                        # successfully summoned to a subreddit (ie, found an
                        # instagram user page link)
                        submission = comment.submission
                        if (
                                # don't try to add if the threshold is negative
                                self.cfg.add_subreddit_threshold >= 0
                                # don't add a duplicate subreddit
                                and submission not in self.subreddits
                        ):
                            self._add_potential_subreddit(submission)

                    self._reply(comment, ig_list)

    def _run_forever(self):
        # XXX: instantiated here so that the _reddit instance is constructed
        # in the child process
        self.filter = Filter(
                self.cfg, self._reddit.username_raw, self.blacklist,
        )
        self.formatter = Formatter(self._reddit.username_raw)

        delay = 1
        while not self._killed.is_set():
            self._process_reply_queue()

            # sleep a bit in case all queues are empty to prevent wasteful CPU
            # spin
            self._killed.wait(delay)


__all__ = [
        'Replier',
]

