from .filter import Filter
from .formatter import Formatter
from .parser import Parser
from constants import PREFIX_USER
from src import reddit
from src.database import (
        InstagramQueueDatabase,
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

    def __init__(self, cfg, rate_limited, blacklist):
        ProcessMixin.__init__(self)
        RedditInstanceMixin.__init__(self, cfg, rate_limited)

        self.blacklist = blacklist
        self.subreddits = SubredditsDatabase()
        self.potential_subreddits = PotentialSubredditsDatabase()
        self.reply_history = ReplyDatabase()
        self.reply_queue = ReplyQueueDatabase()
        self.ig_queue = InstagramQueueDatabase()

    def _enqueue_user(self, ig, comment):
        """
        Enqueues an instagram user to be processed in the future.
        This may happen if instagram is either rate limited or experiencing a
        service outage.
        """
        did_enqueue = False
        msg = ['Queueing \'{color_user}\'']
        if ig.last_id:
            msg.append('@ {last_id}')
        msg.append('from {color_comment}')
        logger.id(logger.debug, self,
                ' '.join(msg),
                color_user=ig.user,
                last_id=ig.last_id,
                color_comment=reddit.display_id(comment),
        )

        try:
            with self.ig_queue:
                self.ig_queue.insert(ig.user, ig.last_id)

        except UniqueConstraintFailed:
            msg = [
                    'Attempted to enqueue duplicate instagram user'
                    ' \'{color_user}\''
            ]
            if ig.last_id:
                msg.append('@ {last_id}')
            msg.append('from {color_comment}')

            logger.id(logger.warn, self,
                    ' '.join(msg),
                    color_user=ig.user,
                    last_id=ig.last_id,
                    color_comment=reddit.display_id(comment),
                    exc_info=True,
            )

        else:
            did_enqueue = True
        return did_enqueue

    def _get_instagram_data(self, ig_usernames, comment):
        """
        Returns a list of instagram data for each user linked-to by the comment
                or None if there were no reply-able instagram usernames found
                    in the comment (this may happen if the program was
                    terminated before it was able to remove the comment from
                    the queue database)
        """

        if not ig_usernames:
            logger.id(logger.debug, self,
                    'No reply-able instagram usernames found in'
                    ' {color_comment}!',
                    color_comment=reddit.display_id(comment),
            )
            return None

        ig_list = []
        for ig_user in ig_usernames:
            if Instagram.is_rate_limited():
                # TODO? logging? could be spammy

                # instagram ratelimited: drop the partially
                # constructed instagram user list so that the bot
                # doesn't reply with a subset of users
                ig_list = []
                break

            last_id = self.ig_queue.get_last_id_for(ig_user)
            ig = Instagram(ig_user, last_id)
            if ig.valid:
                ig_list.append(ig)

            if ig.do_enqueue and ig_user not in self.ig_queue:
                self._enqueue_user(ig, comment)
                # XXX: don't break in case the next user's data can be at
                # least partially fetched. in theory, this could happen if
                # instagram is experiencing spotty outages.

            if 404 in ig.status_codes:
                # linked to a non-existent user; probably a typo but the
                # user could be trying to troll
                self.blacklist.increment_bad_actor(comment)

        # XXX: this check does not prevent the bot from replying with a partial
        # list of instagram users (eg. typo in a link)
        if ig_usernames in self.ig_queue:
            # the bot only fetched data for a subset of the users (or none)

            # TODO? logging? could be spammy

            # don't reply with a partial list of instagram users
            # (either because of ratelimit/instagram server issues)
            ig_list = []

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

        logger.id(logger.debug, self,
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

    def _task_done(self, comment):
        """
        Removes the comment from the reply queue and instagram queue
        """
        if comment in self.reply_queue:
            with self.reply_queue:
                self.reply_queue.delete(comment)

        ig_usernames = Parser(comment).ig_usernames
        if ig_usernames in self.ig_queue:
            with self.ig_queue:
                self.ig_queue.delete(ig_usernames)

    def _process_reply_queue(self):
        while not self._killed.is_set() and self.reply_queue.size() > 0:
            data = self.reply_queue.get()
            if not data:
                # queue is empty
                break

            comment_id, mention_id = data
            comment = self._reddit.comment(comment_id)
            mention = None
            if mention_id:
                mention = self._reddit.comment(mention_id)

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

            ig_list = self._get_instagram_data(ig_usernames, comment)
            if ig_list:
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

                # don't remove only on successful reply since the bot may be
                # ratelimited from sending replies (in which case the ratelimit
                # handler should eventually get around to posting it)
                self._task_done(comment)

            elif ig_usernames not in self.ig_queue:
                # XXX: bad-actor flagging from mentions temporarily(?) turned
                # off because linking to an invalid instagram page is not
                # necessarily indicative of bad behavior. plus, trolling the bot
                # doesn't really have any sort of feedback for the offending
                # user so I doubt it'll be (much of) an issue.

                # all linked instagram users were invalid
                # if mention and not Instagram.is_rate_limited():
                #     # summoned to a submission with comment(s) linking to
                #     # invalid instagram users
                #     self.blacklist.increment_bad_actor(mention)

                self._task_done(comment)

            else:
                # the comment was queued
                break

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

