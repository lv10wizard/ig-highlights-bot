from praw.models import Comment

from .parser import Parser
from src import (
        database,
        reddit,
)
from src.util import logger


class Filter(object):
    """
    Filters things that the bot should make replies to
    """

    def __init__(self, cfg, username, blacklist):
        self.cfg = cfg
        self.blacklist = blacklist
        # username should be the raw username string (ie, no 'u/')
        self.username = username
        self.reply_history = database.ReplyDatabase()
        self.reply_queue = database.ReplyQueueDatabase()
        self.reddit_ratelimit_queue = database.RedditRateLimitQueueDatabase()

    def __str__(self):
        result = [self.__class__.__name__]
        if self.username:
            result.append(self.username)
        return ':'.join(result)

    def _by_me(self, comment):
        """
        Returns True if the comment was posted by the bot
        """
        result = False
        # author may be None if deleted/removed
        if bool(comment.author):
            author = comment.author.name.lower()
            result = author == self.username.lower()
        return result

    def _can_reply(self, thing):
        """
        Checks if the bot is able to make a reply to the thing.
        This does not mean that the thing contains any content that the bot
        will want to reply to.

        Returns True if
            - thing not already replied to by the bot
            - thing already queued for a reply
            - thing is not in the rate-limit queue
            - the bot has not replied too many times to the submission (too many
              defined in config)
            - thing not archived (too old)
            - thing not itself posted by the bot
            - thing not in a blacklisted subreddit or posted by a blacklisted
              user
        """
        # XXX: the code is fully written out instead of being a simple boolean
        # (eg. return not (a or b or c)) so that appropriate logging calls can
        # be made

        # check the database first (guaranteed to incur no network request)
        already_replied = self.reply_history.has_replied(thing)
        if already_replied:
            logger.id(logger.debug, self,
                    'I already replied to {color_thing}: skipping.',
                    color_thing=reddit.display_id(thing),
            )
            return False

        if thing in self.reply_queue:
            # already queued for a reply; not sure how this would happen
            logger.id(logger.debug, self,
                    '{color_thing} is already queued for a reply: skipping.',
                    color_thing=reddit.display_id(thing),
            )
            return False

        if thing in self.reddit_ratelimit_queue:
            # will be handled by the RateLimitHandler
            logger.id(logger.debug, self,
                    '{color_thing} is rate-limit queued: skipping.',
                    color_thing=reddit.display_id(thing),
            )
            return False

        submission = reddit.get_submission_for(thing)
        replied = self.reply_history.replied_things_for_submission(submission)
        if len(replied) > self.cfg.max_replies_per_post:
            logger.id(logger.debug, self,
                    'I\'ve made too many replies (#{num}) to {color_post}:'
                    ' skipping.',
                    num=self.cfg.max_replies_per_post,
                    color_post=reddit.display_id(submission),
            )
            return False

        # potentially spammy
        if hasattr(thing, 'archived') and thing.archived:
            logger.id(logger.debug, self,
                    '{color_thing} is too old: skipping.',
                    color_thing=reddit.display_id(thing),
            )

        if self._by_me(thing):
            logger.id(logger.debug, self,
                    'I posted {color_thing}: skipping.',
                    color_thing=reddit.display_id(thing),
            )
            return False

        # XXX: there is the possibility that the blacklist check fails just as
        # that account/subreddit becomes blacklisted
        #   eg. 1. user requests to be blacklisted
        #       2. bot finds comment & sees not blacklisted
        #       3. messages process adds user to blacklist
        #       4. bot replies to comment
        # .. should only cause one erroneous reply once blacklisted (and only in
        # this rare situation)
        prefixed_name = self.blacklist.is_blacklisted_thing(thing)
        if prefixed_name:
            time_left = self.blacklist.time_left_seconds_name(prefixed_name)

            msg = []
            msg.append('{color_name} is blacklisted')
            if time_left > 0:
                msg.append('for {time}')
            msg.append('({color_thing}):')
            msg.append('skipping.')

            # potentially spammy (for subreddits)
            # TODO? don't log if is_subreddit
            logger.id(logger.debug, self,
                    ' '.join(msg),
                    color_name=prefixed_name,
                    time=time_left,
                    color_thing=reddit.display_id(thing),
            )
            return False
        return True

    def _prune_already_posted_users(self, submission, ig_usernames):
        """
        Removes instagram usernames that the bot has already posted to the
        given submission (or usernames that are currently queued to be posted
        in the submission).

        Returns a subset of the passed-in instagram usernames (the returned
                set will be less than or equal to the passed-in set)
        """
        orig_usernames = ig_usernames.copy()
        already_posted = self.reply_history.replied_ig_users_for_submission(
                submission
        )
        if already_posted:
            logger.id(logger.debug, self,
                    'Already posted in {color_submission}: {color_users}',
                    color_submission=reddit.display_id(submission),
                    color_users=already_posted,
            )

        currently_queued = self.reddit_ratelimit_queue.ig_users_for(submission)
        if currently_queued:
            logger.id(logger.debug, self,
                    'Currently queued for {color_submission}: {color_users}',
                    color_submission=reddit.display_id(submission),
                    color_users=currently_queued,
            )

        skip = list(already_posted | currently_queued)
        ig_usernames = [user for user in ig_usernames if user not in skip]

        # XXX: reconstruct the pruned list so that the order is kept
        pruned = [user for user in orig_usernames if user not in ig_usernames]
        if pruned:
            msg = ['Pruned #{num_posted} usernames: {color_posted}']
            if ig_usernames:
                msg.append('#{num_users}: {color_users}')
            else:
                msg.append('All users pruned!')
            logger.id(logger.debug, self,
                    '\n\t'.join(msg),
                    num_posted=len(pruned),
                    color_posted=pruned,
                    num_users=len(ig_usernames),
                    color_users=ig_usernames,
            )
        return ig_usernames

    def _too_many_replies_in_thread(self, comment):
        """
        Returns True if the bot has made too many replies in the comment thread

        (This is separate from _can_reply because, depending on the depth of the
         comment, it may trigger multiple network hits)
        """
        if not isinstance(comment, Comment):
            return False

        too_many_replies = False
        ancestor_tree = reddit.get_ancestor_tree(comment)
        if ancestor_tree:
            author_tree = [
                    c.author.name.lower()
                    # XXX: specifically insert None for comments
                    # missing authors (deleted/removed)
                    if bool(c.author) else None
                    for c in ancestor_tree
            ]
        else:
            author_tree = []

        logger.id(logger.debug, self,
                '{color_comment} author tree:'
                ' [#{num}] {color}',
                color_comment=reddit.display_id(comment),
                num=len(author_tree),
                color=author_tree,
        )

        num_comments_by_me = author_tree.count(self.username.lower())
        if num_comments_by_me > self.cfg.max_replies_in_comment_thread:
            logger.id(logger.debug, self,
                    'I\'ve made too many replies in'
                    ' {color_comment}\'s thread: skipping.',
                    color_comment=reddit.display_id(comment),
            )
            too_many_replies = True
        return too_many_replies

    def replyable_usernames(
            self, thing, prelim_check=True, check_thread=True
    ):
        """
        Returns a list of instagram usernames contained in the thing that the
        bot can reply to or an empty list if the bot cannot reply to the thing
        for any reason.

        prelim_check (bool, optional) - whether preliminary thing checks
                should be preformed. If this is False, the thing will be
                parsed for usernames without first checking _can_reply.
        check_thread (bool, optional) - whether the thing thread should be
                checked for too many bot replies (this is an expensive operation
                in terms of reddit's ratelimit)
        """
        usernames = []
        # filter out things that the bot cannot reply to
        if thing and (not prelim_check or self._can_reply(thing)):
            parsed_thing = Parser(thing)
            thing_usernames = parsed_thing.ig_usernames
            # filter out things that contain no instagram usernames
            if thing_usernames:
                new_usernames = self._prune_already_posted_users(
                        reddit.get_submission_for(thing), thing_usernames,
                )
                # filter out instagram usernames that the bot has already
                # replied to in this submission
                if new_usernames:
                    too_many_replies = False
                    if check_thread:
                        too_many_replies = self._too_many_replies_in_thread(
                                thing,
                        )
                    # filter out comment threads that the bot has made too many
                    # replies to
                    if not too_many_replies:
                        usernames = new_usernames

        return usernames

    # TODO? move; this doesn't really belong here ...
    def enqueue(self, thing, ig_usernames, mention=None):
        """
        Enqueues a thing for the bot to reply to

        Returns True if the thing was successfully queued
        """
        success = False

        logger.id(logger.info, self,
                'Queueing {color_thing} into reply-queue ...',
                color_thing=reddit.display_id(thing),
        )

        try:
            with self.reply_queue:
                self.reply_queue.insert(thing, mention)

        except database.UniqueConstraintFailed:
            logger.id(logger.warn, self,
                    'Attempted to queue duplicate replyable thing:'
                    ' {color_thing} ({color_users})',
                    color_thing=reddit.display_id(thing),
                    color_users=ig_usernames,
                    exc_info=True,
            )

        else:
            success = True
        return success


__all__ = [
        'Filter',
]

