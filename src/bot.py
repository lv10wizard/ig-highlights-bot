import multiprocessing
import Queue
import re
import signal

import praw
from praw.models import Comment
from prawcore.exceptions import (
        Forbidden,
        OAuthException,
        Redirect,
)
from utillib import logger

from src import (
        blacklist,
        comments,
        config,
        instagram,
        mentions,
        messages,
        reddit,
        replies,
)
from src.database import ReplyDatabase


class IgHighlightsBot(object):
    """
    """

    def __init__(self, cfg):
        signal.signal(signal.SIGINT, self.graceful_exit)
        signal.signal(signal.SIGTERM, self.graceful_exit)

        self._killed = False
        self.cfg = cfg
        self.reply_history = ReplyDatabase(self.cfg.replies_db_path)
        self.blacklist = blacklist.Blacklist(self.cfg)
        self.messages = messages.Messages(
                cfg=cfg,
                blacklist=self.blacklist,
        )
        # queue of submissions to be processed (produced through separate
        # processes -- eg. summoned to post through user mention)
        self.submission_queue = multiprocessing.JoinableQueue()
        # self.mentions = mentions.Mentions(self.submission_queue)

        self._reddit = reddit.Reddit(cfg)

        # initialize stuff that require correct credentials
        self._formatter = replies.Formatter(self._reddit.username_raw)

    def __str__(self):
        return self._reddit.username_raw

    def graceful_exit(self, signum=None, frame=None):
        """
        """
        # https://stackoverflow.com/a/2549950
        signames = {
                num: name for name, num in
                reversed(sorted(signal.__dict__.iteritems()))
                if name.startswith('SIG') and not name.startswith('SIG_')
        }

        msg = []
        if signum:
            msg.append('Caught {name} ({num})!')
        msg.append('Shutting down ...')

        try:
            logger.prepend_id(logger.debug, self,
                    ' '.join(msg),
                    name=signames[signum] if signum is not None else '???',
                    num=signum,
            )
        except KeyError as e:
            # signum doesn't match a signal specified in the signal module ...?
            # this is probably not possible
            logger.prepend_id(logger.debug, self,
                    ' '.join(msg),
                    name='???',
                    num=signum,
            )

        # TODO: kill (+join) subprocesses

        # XXX: kill the main process last so that daemon processes aren't
        # killed at inconvenient times
        self._killed = True

    def reply(self, comment, ig_list, callback_depth=0):
        """
        Reply to a single comment with (potentially) multiple instagram user
        highlights
        """
        logger.prepend_id(logger.debug, self,
                '{depth}Replying to {color_comment}: {unpack_color}',
                depth=(
                    '[#{0}] '.format(callback_depth)
                    if callback_depth > 0
                ),
                color_comment=reddit.display_id(comment),
                unpack_color=ig_list,
        )

        reply_text_list = self._formatter.format(
                ig_list, self.cfg.num_highlights_per_ig_user
        )
        if len(reply_text_list) > self.cfg.max_replies_per_comment:
            logger.prepend_id(logger.debug, self,
                    '{color_comment} ({color_author}) almost made me reply'
                    ' #{num} times: skipping.',
                    color_comment=reddit.display_id(comment),
                    color_author=(
                        comments.author.name.lower()
                        if comments.author
                        # can this happen? (no author but has body text)
                        else '[deleted/removed]'
                    ),
                    num=len(reply_text_list),
            )
            # TODO? temporarily blacklist (O(days)) user? could be trying to
            # break the bot. or could just be a comment with a lot of instagram
            # profile links.
            return

        for body, ig_users in reply_text_list:
            if reddit.do_reply(comment, body):
                self.reply_history.insert(comment, ig_users)

    def by_me(self, comment):
        """
        Returns True if the comment was posted by the bot
        """
        result = False
        # author may be None if deleted/removed
        if bool(comment.author):
            author = comment.author.name.lower()
            result = author == self._reddit.username_raw.lower()
        return result

    def can_reply(self, comment):
        """
        Returns True if
            - comment not already replied to by the bot
            - the bot has not replied too many times to the submission (too many
              defined in config)
            - comment not archived (too old)
            - comment not itself posted by the bot
            - comment not in a blacklisted subreddit or posted by a blacklisted
              user
        """
        # XXX: the code is fully written out instead of being a simple boolean
        # (eg. return not (a or b or c)) so that appropriate logging calls can
        # be made

        # check the database first (guaranteed to incur no network request)
        already_replied = self.reply_history.has_replied(comment)
        if already_replied:
            logger.prepend_id(logger.debug, self,
                    'I already replied to {color_comment}: skipping.',
                    color_comment=reddit.display_id(comment),
            )
            return False

        replied = self.reply_history.replied_comments_for_submission(
                comment.submission
        )
        if len(replied) > self.cfg.max_replies_per_post:
            logger.prepend_id(logger.debug, self,
                    'I\'ve made too many replies (#{num}) to {color_post}:'
                    ' skipping.',
                    num=self.cfg.max_replies_per_post,
                    color_post=reddit.display_id(comment.submission),
            )
            return False

        # potentially spammy
        if comment.archived:
            logger.prepend_id(logger.debug, self,
                    '{color_comment} is too old: skipping.',
                    color_comment=reddit.display_id(comment),
            )

        by_me = self.by_me(comment)
        if by_me:
            logger.prepend_id(logger.debug, self,
                    'I posted {color_comment}: skipping.',
                    color_comment=reddit.display_id(comment),
            )
            return False

        # XXX: there is the possibility that the blacklist check fails just as
        # that account/subreddit becomes blacklisted
        #   eg. 1. user requests to be blacklisted
        #       2. bot finds comment & sees not blacklisted
        #       3. messages process adds user to blacklist
        #       4. bot replies to comment
        # .. should only cause one erroneous reply post-blacklist (and only in
        # this rare situation)
        prefixed_name = self.blacklist.is_blacklisted_thing(comment)
        if prefixed_name:
            time_left = self.blacklist.time_left_seconds_name(prefixed_name)

            msg = []
            msg.append('{color_name} is blacklisted')
            if time_left > 0:
                msg.append('for {time}')
            msg.append('({color_comment}):')
            msg.append('skipping.')

            # potentially spammy (for subreddits)
            # TODO? don't log if is_subreddit
            logger.prepend_id(logger.debug, self,
                    ' '.join(msg),
                    color_name=prefixed_name,
                    time=time_left,
                    color_comment=reddit.display_id(comment),
            )
            return False
        return True

    def prune_already_posted_users(self, submission, ig_usernames):
        """
        """
        already_posted = self.reply_history.replied_ig_users_for_submission(
                submission
        )
        pruned = ig_username.intersection(already_posted)
        ig_usernames -= already_posted
        if pruned:
            logger.prepend_id(logger.debug, self,
                    'Pruned #{num_posted} usernames: {unpack_color_posted}'
                    '\n\t#{num_users}: {unpack_color_users}',
                    num_posted=len(pruned),
                    unpack_color_posted=pruned,
                    num_users=len(ig_usernames),
                    unpack_color_users=ig_usernames,
            )
        return ig_usernames

    def get_ancestor_tree(self, comment, to_lower=True):
        """
        Returns a list of comments starting with the parent of the given
        comment, traversing up until the root comment is hit. That is, the list
        is ordered from parent [0] -> root [N-1]. In other words, a reversed
        comment tree.

        comment (praw.models.Comment) - the comment to get the ancestors of
        to_lower (bool, optional) - whether the list results should be lower-
                                    cased
        """

        # TODO? cache results for each comment-id hit to potentially lower
        # number of requests made (in the unlikely event that we need the
        # ancestors of a sibling this comment)

        # https://praw.readthedocs.io/en/latest/code_overview/models/comment.html#praw.models.Comment.parent
        result = []
        ancestor = comment
        refresh_counter = 0
        while not ancestor.is_root:
            ancestor = ancestor.parent()
            result.append(ancestor)
            if refresh_counter % 9 == 0:
                ancestor.refresh()
            refresh_counter += 1

        logger.prepend_id(logger.debug, self,
                '{color_comment} ancestor authors: [#{num}] {unpack_color}',
                color_comment=reddit.display_id(comment),
                num=len(result),
                unpack_color=result,
        )
        return result

    def process_submission_queue(self, num=5):
        """
        Tries to process num elements in the submission_queue

        num (int, optional) - number of elements to process (halts if the queue
                is empty regardless of number of elements processed).
        """
        if not isinstance(num, int) or num < 0:
            num = 5

        try:
            for i in xrange(num):
                submission = self.submission_queue.get_nowait()
                logger.prepend_id(logger.debug, self,
                        '[{i}/{num}] Processing submission {color_submission}'
                        ' (#{qnum} remaining) ...',
                        i=i+1,
                        num=num,
                        color_submission=submission,
                        qnum=self.submission_queue.qsize(),
                )

                for comment in submission.comments.list():

                    # -----
                    # TODO: move to function so that run_forever can reuse
                    if comment and self.can_reply(comment):
                        parsed_comment = comments.Parser(comment)
                        ig_usernames = self.prune_already_posted_users(
                                comment.submission,
                                parsed_comment.ig_usernames,
                        )
                        if ig_usernames:
                            ancestor_tree = self.get_ancestor_tree(comment)
                            author_tree = [
                                    c.author.name.lower()
                                    # XXX: specifically insert None for comments
                                    # missing authors (deleted/removed)
                                    if bool(c.author) else None
                                    for c in ancestor_tree
                            ]

                            logger.prepend_id(logger.debug, self,
                                    '{color_comment} author tree:'
                                    ' [#{num}] {unpack_color}',
                                    color_comment=reddit.display_id(comment),
                                    num=len(author_tree),
                                    unpack_color=author_tree,
                            )

                            num_comments_by_me = author_tree.count(
                                    self._reddit.username_raw.lower()
                            )
                            max_by_me = self.cfg.max_replies_in_comment_thread
                            if num_comments_by_me > max_by_me:
                                logger.prepend_id(logger.debug, self,
                                        'I\'ve made too many replies in'
                                        ' {color_comment}\'s thread: skipping.',
                                        color_comment=reddit.display_id(
                                            comment
                                        ),
                                )
                                continue # TODO: change to 'return'

                            ig_list = [
                                    instagram.Instagram(ig_user)
                                    for ig_user in ig_usernames
                            ]
                            # TODO: examine if any 404 or otherwise invalid
                            # & increment comment.author.name.lower()'s
                            # to_blacklist count
                            #   if count > threshold => add to temporary blacklist
                            #       ( temporary as in O(days) )
                            # >>> store to_blacklist in memory?
                            self.reply(comment, ig_list)
                    # -----

                self.submission_queue.task_done()

        except Queue.Empty:
            pass

    def run_forever(self):
        """
        """
        # TODO: start inbox message parsing process
        # TODO: start mentions parser process
        subs = self._reddit.subreddit(self.subs)
        comment_stream = subs.stream.comments(pause_after=0)
        try:
            while not self._killed:
                # TODO: can GETs cause praw to throw a ratelimit exception?
                for comment in comment_stream:
                    # TODO: self._consider_reply(comment) .. maybe name
                    # something better

                    if not comment:
                        break

                self.process_submission_queue()

        except Redirect as e:
            if re.search(r'/subreddits/search', e.message):
                logger.prepend_id(logger.error, self,
                        'One or more non-existent subreddits:'
                        ' {unpack_color}', e, True,
                        unpack_color=subs.split('+'),
                )

        finally:
            logger.prepend_id(logger.info, self,
                    'Exiting ...',
            )


__all__ = [
        'IgHighlightsBot',
]

