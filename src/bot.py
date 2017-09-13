from getpass import getpass
import multiprocessing
import os
import pprint
import Queue
import re
import signal
import sys
import time
from urlparse import urlparse

import praw
from praw.models import Comment
from prawcore.exceptions import (
        Forbidden,
        OAuthException,
        Redirect,
)
from utillib import logger

from constants import (
        AUTHOR,
        KEY_BLACKLIST_NAME,
        KEY_BLACKLIST_ADD,
        KEY_BLACKLIST_REMOVE,
        PREFIX_SUBREDDIT,
        PREFIX_USER,
)
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

    COMMENT_CHARACTER_LIMIT = 1e4 # 10 000

    def __init__(self, cfg):
        signal.signal(signal.SIGINT, self.graceful_exit)
        signal.signal(signal.SIGTERM, self.graceful_exit)

        self.cfg = cfg
        self.reply_history = ReplyDatabase(self.cfg.replies_db_path)
        self.blacklist = blacklist.Blacklist(self.cfg)
        self.messages = messages.Messages(
                cfg=cfg,
                blacklist=self.blacklist,
        )

        self._reddit = praw.Reddit(
                site_name=self.cfg.praw_sitename,
                user_agent=self.user_agent,
        )
        self.try_set_username()
        self.try_set_password()

        # try to auth immediately to catch anything wrong with credentials
        try:
            self._reddit.user.me()

        except OAuthException as e:
            logger.prepend_id(logger.error, self,
                    'Login failed! Please check that praw.ini contains the'
                    ' correct login information under the section:'
                    ' \'[{section}]\'', e, True,
                    section=self.cfg.praw_sitename,
            )

        # initialize stuff that require correct credentials
        self._formatter = replies.Formatter(self._reddit.config)

        # queue of submissions to be processed (produced through separate
        # processes -- eg. summoned to post through user mention)
        self.submission_queue = multiprocessing.JoinableQueue()
        # self.mentions = mentions.Mentions(self.submission_queue)

        logger.prepend_id(logger.debug, self,
                'client id: {client_id}'
                '\nuser name: {username}'
                '\nuser agent: {user_agent}',
                client_id=self._reddit.config.client_id,
                username=self.username_raw,
                user_agent=self.user_agent,
        )

    def __str__(self):
        return self.username_raw

    def graceful_exit(self, signum=None, frame=None):
        """
        """
        pass # TODO

    def try_set_username(self):
        """
        Asks the user to enter the bot account username if not defined in
        praw.ini
        """
        if isinstance(self._reddit.config.username, praw.config._NotSet):
            self._reddit.config.username = raw_input('bot account username: ')
            self.warn_if_wrong_praw_version()
            self._reddit._prepare_prawcore()

    def try_set_password(self):
        """
        Asks the user to enter the bot account password if it was not defined
        in praw.ini
        """
        while isinstance(self._reddit.config.password, praw.config._NotSet):
            first = getpass('{0} password: '.format(self.username))
            second = getpass('Re-enter password: ')
            if first == second:
                self._reddit.config.password = first

                # https://github.com/praw-dev/praw/blob/master/praw/reddit.py
                # XXX: praw's Config.password is just a member variable; setting
                # it does not actually allow authentication if the password
                # is set after Reddit.__init__
                self.warn_if_wrong_praw_version()
                # the following call works as of praw 5.1 (may break in later
                # versions)
                self._reddit._prepare_prawcore()
            else:
                logger.prepend_id(logger.warn, self,
                        'Passwords do not match! Please try again.',
                )

    def warn_if_wrong_praw_version(self):
        major, minor, revision = praw.__version__.split('.')
        try:
            major = int(major)
            minor = int(minor)
            revision = int(revision)
        except ValueError as e:
            # something went horribly wrong
            logger.prepend_id(logger.error, self,
                    'Failed to determine praw version!', e, True,
            )
        else:
            if not (major == 5 and minor == 1 and revision == 0):
                logger.prepend_id(logger.warn, self,
                        'praw version != 5.1.0 (version={ver});'
                        ' authentication may fail!',
                        ver=praw.__version__,
                )

    @property
    def username_raw(self):
        return self._reddit.config.username

    @property
    def username(self):
        return reddit.prefix_user(self.username_raw)

    @property
    def user_agent(self):
        """
        Memoized user agent string
        """
        try:
            user_agent = self.__user_agent
        except AttributeError:
            version = '0.1' # TODO: read from file
            self.__user_agent = (
                    '{platform}:{appname}:{version} (by {prefix}{author})'
            ).format(
                    platform=sys.platform,
                    appname=self.cfg.app_name,
                    version=version,
                    prefix=PREFIX_USER,
                    author=AUTHOR,
            )
            user_agent = self.__user_agent
        return user_agent

    def reply(self, comment, ig_list, callback_depth=0):
        """
        Reply to a single comment with (potentially) multiple instagram user
        highlights
        """
        logger.prepend_id(logger.debug, self,
                '',
        )

        reply_text_list = self._formatter.format(
                ig_list, self.cfg.num_highlights_per_ig_user
        )
        if len(reply_text_list) > self.cfg.max_replies_per_comment:
            logger.prepend_id(logger.debug, self,
                    '{color_comment} ({color_author}) almost made me reply'
                    ' #{num} times: skipping.',
                    color_comment=comments.display_id(comment),
                    color_author=(
                        comments.author.name.lower()
                        if comments.author
                        # can this happen? (no author but has body text)
                        else '[deleted/removed]'
                    ),
                    num=len(reply_text_list),
            )
            # TODO? temporarily blacklist (O(days)) user? could be trying to
            # break the bot
            return

        logger.prepend_id(logger.debug, self,
                'Replying to {color_comment}:\n{reply}',
                color_comment=comments.display_id(comment),
                reply='\n\n'.join(reply_text_list),
        )

        try:
            # TODO: comment.reply(...)
            pass

        except Forbidden as e:
            logger.prepend_id(logger.error, self,
                    'Failed to reply to comment {color_comment}!', e, True,
                    color_comment=comments.display_id(comment),
            )

        except praw.exceptions.APIException as e:
            # TODO: map APIException handlers to their corresponding error_type
            #   - ratelimit
            #   - too_old
            #   - no_text
            #   - no_links
            self._handle_rate_limit(
                    err=e,
                    depth=callback_depth,
                    callback=self.reply,
                    callback_kwargs={
                        'comment': comment,
                        'ig_list': ig_list,
                        'callback_depth': callback_depth+1,
                    },
            )

        else:
            self.reply_history.insert(comment, ig_list)

    def _handle_rate_limit(self, err, depth, callback, callback_args=(),
            callback_kwargs={},
    ):
        """
        """
        if depth > 10:
            # (N+1)-th try in chain.. something is wrong
            raise

        if (
                hasattr(err, 'error_type')
                and isinstance(err.error_type, basestring)
                and err.error_type.lower() == 'ratelimit'
        ):
            delay = 10 * 60

            logger.prepend_id(logger.debug, self,
                    '{error_type}: trying to find proper delay ...',
                    error_type=err.error_type,
            )
            try:
                delay = config.parse_time(err.message)

            except config.InvalidTime:
                logger.prepend_id(logger.debug, self,
                        'Failed to set appropriate delay;'
                        ' using default ({time})',
                        time=delay,
                )

            else:
                logger.prepend_id(logger.debug, self,
                        'Found rate-limit delay: {time}',
                        time=parsed_delay,
                )

            logger.prepend_id(logger.error, self,
                    'Rate limited! Retrying \'{callback}\' in {time} ...', err,
                    callback=callback.__name__,
                    time=delay,
            )
            time.sleep(delay)
            callback(*callback_args, **callback_kwargs)

        else:
            raise

    def by_me(self, comment):
        """
        Returns True if the comment was posted by the bot
        """
        return (
                # in case of deleted/removed
                bool(comment.author)
                and comment.author.name.lower() == self.username_raw.lower()
        )

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
                    color_comment=comments.display_id(comment),
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
                    color_post=comments.display_id(comment.submission),
            )
            return False

        # potentially spammy
        if comment.archived:
            logger.prepend_id(logger.debug, self,
                    '{color_comment} is too old: skipping.',
                    color_comment=comments.display_id(comment),
            )

        by_me = self.by_me(comment)
        if by_me:
            logger.prepend_id(logger.debug, self,
                    'I posted {color_comment}: skipping.',
                    color_comment=comments.display_id(comment),
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
                    color_comment=comments.display_id(comment),
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
                color_comment=comments.display_id(comment),
                num=len(result),
                unpack_color=result,
        )
        return result

    def process_submission_queue(self, num=1):
        """
        Tries to process num elements in the submission_queue

        num (int, optional) - number of elements to process (halts if the queue
                                is empty regardless of number of elements
                                processed).
        """
        if not isinstance(num, int) or num < 0:
            num = 1

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
                                    color_comment=comments.display_id(comment),
                                    num=len(author_tree),
                                    unpack_color=author_tree,
                            )

                            num_comments_by_me = author_tree.count(
                                    self.username_raw.lower()
                            )
                            max_by_me = self.cfg.max_replies_in_comment_thread
                            if num_comments_by_me > max_by_me:
                                logger.prepend_id(logger.debug, self,
                                        'I\'ve made too many replies in'
                                        ' {color_comment}\'s thread: skipping.',
                                        color_comment=comments.display_id(
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
        try:
            for comment in subs.stream.comments(pause_after=0):
                # process a single submission from a producer process
                # (eg. summoned through user mention)
                self.process_submission_queue()

                # TODO: self._consider_reply(comment) .. maybe name something better

        except Redirect as e:
            if re.search(r'/subreddits/search', e.message):
                logger.prepend_id(logger.error, self,
                        'One or more non-existent subreddits:'
                        ' {unpack_color}', e, True,
                        unpack_color=subs.split('+'),
                )


__all__ = [
        'IgHighlightsBot',
]

