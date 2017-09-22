import multiprocessing
import os
import re
import signal
import time

from prawcore.exceptions import Redirect
from six import iteritems
from six.moves import queue

from constants import SUBREDDITS_DEFAULTS_PATH
from src import (
        blacklist,
        comments,
        instagram,
        mentions,
        messages,
        reddit,
        replies,
)
from src.database import (
        BadActorsDatabase,
        InstagramQueueDatabase,
        PotentialSubredditsDatabase,
        ReplyDatabase,
        SubredditsDatabase,
        UniqueConstraintFailed,
)
from src.mixins import StreamMixin
from src.util import logger


class IgHighlightsBot(StreamMixin):
    """
    """

    def __init__(self, cfg):
        signal.signal(signal.SIGINT, self.graceful_exit)
        signal.signal(signal.SIGTERM, self.graceful_exit)

        StreamMixin.__init__(self, cfg)

        self._killed = False
        self.reply_history = ReplyDatabase(cfg.replies_db_path)
        self.subreddits = SubredditsDatabase(
                path=cfg.subreddits_db_path,
                do_seed=(not os.path.exists(SUBREDDITS_DEFAULTS_PATH)),
        )
        self.potential_subreddits = PotentialSubredditsDatabase(
                path=cfg.potential_subreddits_db_path,
        )
        self.bad_actors = BadActorsDatabase(cfg.bad_actors_db_path, cfg)
        self.blacklist = blacklist.Blacklist(cfg)
        self.ig_queue = InstagramQueueDatabase(cfg.instagram_queue_db_path)

        self.messages = messages.Messages(cfg, self.blacklist)
        # queue of submissions to be processed (produced through separate
        # processes -- eg. summoned to post through user mention)
        self.submission_queue = multiprocessing.JoinableQueue()
        self.mentions = mentions.Mentions(cfg, self.submission_queue)

        # initialize stuff that requires correct credentials
        instagram.Instagram.initialize(cfg, self._reddit.username)
        self._formatter = replies.Formatter(self._reddit.username_raw)

    def __str__(self):
        return self._reddit.username_raw

    def graceful_exit(self, signum=None, frame=None):
        """
        """
        # https://stackoverflow.com/a/2549950
        signames = {
                num: name for name, num in
                reversed(sorted(iteritems(signal.__dict__)))
                if name.startswith('SIG') and not name.startswith('SIG_')
        }

        msg = []
        if signum:
            msg.append('Caught {name} ({num})!')
        msg.append('Shutting down ...')

        try:
            logger.id(logger.debug, self,
                    ' '.join(msg),
                    name=signames[signum] if signum is not None else '???',
                    num=signum,
            )
        except KeyError as e:
            # signum doesn't match a signal specified in the signal module ...?
            # this is probably not possible
            logger.id(logger.debug, self,
                    ' '.join(msg),
                    name='???',
                    num=signum,
            )

        self.messages.kill()
        self.mentions.kill()
        self.messages.join()
        self.mentions.join()

        # XXX: kill the main process last so that daemon processes aren't
        # killed at inconvenient times
        self._killed = True

    def _increment_bad_actor(self, thing, data):
        if thing.author:
            logger.id(logger.debug, self,
                    'Incrementing {color_author}\'s bad actor count',
                    color_author=thing.author.name,
            )

            try:
                with self.bad_actors:
                    self.bad_actors.insert(thing, data)

            except UniqueConstraintFailed:
                logger.id(logger.debug, self,
                        '{color_author} already flagged as a bad actor for'
                        '{color_thing}!',
                        color_author=thing.author.name,
                        color_thing=reddit.display_id(thing),
                )

    def _reply(self, comment, ig_list, callback_depth=0):
        """
        Reply to a single comment with (potentially) multiple instagram user
        highlights

        Returns True if successfully replied one or more times
        """
        success = False

        logger.id(logger.debug, self,
                '{depth}Replying to {color_comment}: {color}',
                depth=(
                    '[#{0}] '.format(callback_depth)
                    if callback_depth > 0 else ''
                ),
                color_comment=reddit.display_id(comment),
                color=ig_list,
        )

        reply_text_list = self._formatter.format(ig_list)
        if len(reply_text_list) > self.cfg.max_replies_per_comment:
            logger.id(logger.debug, self,
                    '{color_comment} ({color_author}) almost made me reply'
                    ' #{num} times: skipping.',
                    color_comment=reddit.display_id(comment),
                    color_author=(
                        comment.author.name.lower()
                        if comment.author
                        # can this happen? (no author but has body text)
                        else '[deleted/removed]'
                    ),
                    num=len(reply_text_list),
            )
            # TODO? temporarily blacklist (O(days)) user? could be trying to
            # break the bot. or could just be a comment with a lot of instagram
            # profile links.
            #   - store comment.permalink()
            #       ie, self.bad_actors.insert(comment, comment.permalink())
            #       (.permalink() may be a network hit)
            return

        did_insert = False
        for body, ig_users in reply_text_list:
            if reddit.do_reply(comment, body):
                self.reply_history.insert(comment, ig_users)
                did_insert = True
        if did_insert:
            self.reply_history.commit()
            # XXX: only one required to succeed for method to be considered
            # success
            success = True

        return success

    def reply(self, comment):
        """
        Attempts to reply to a comment with instagram user highlights.
        This will only reply if enough conditions are met (eg. hasn't replied to
        the specific post too many times, isn't in a blacklisted subreddit or
        comment not made by a blacklisted user, etc)

        Returns (reply_attempted, did_reply), a tuple of bools
                reply_attempted = lenient "success" flag; this indicates that
                        the reply did not explicitly fail
                did_reply = explicit success flag (a reply was made)
        """

        reply_attempted = True
        did_reply = False
        if comment and self.can_reply(comment):
            parsed_comment = comments.Parser(comment)
            ig_usernames = self.prune_already_posted_users(
                    comment.submission,
                    parsed_comment.ig_usernames,
            )
            if ig_usernames:
                ancestor_tree = reddit.get_ancestor_tree(comment)
                author_tree = [
                        c.author.name.lower()
                        # XXX: specifically insert None for comments
                        # missing authors (deleted/removed)
                        if bool(c.author) else None
                        for c in ancestor_tree
                ]

                logger.id(logger.debug, self,
                        '{color_comment} author tree:'
                        ' [#{num}] {color}',
                        color_comment=reddit.display_id(comment),
                        num=len(author_tree),
                        color=author_tree,
                )

                num_comments_by_me = author_tree.count(
                        self._reddit.username_raw.lower()
                )
                if num_comments_by_me > self.cfg.max_replies_in_comment_thread:
                    logger.id(logger.debug, self,
                            'I\'ve made too many replies in'
                            ' {color_comment}\'s thread: skipping.',
                            color_comment=reddit.display_id(comment),
                    )

                else:
                    ig_list = []
                    queued_ig_data = self.ig_queue.get_ig_data_for(comment)
                    for ig_user in ig_usernames:
                        is_rate_limited = instagram.Instagram.is_rate_limited()
                        if is_rate_limited:
                            # drop the ig_list so that no reply attempt is made
                            ig_list = []
                            break

                        if ig_user in queued_ig_data:
                            last_id = queued_ig_data[ig_user]
                        ig = instagram.Instagram(ig_user, last_id)
                        if ig.valid:
                            ig_list.append(ig)

                        if (
                                ig.do_enqueue
                                # don't try to requeue a duplicate entry
                                and not self.ig_queue.is_queued(
                                    ig_user, comment
                                )
                        ):
                            msg = ['Queueing \'{user}\'']
                            if ig.last_id:
                                msg.append('(@ {last_id})')
                            msg.append('from {color_comment}')
                            logger.id(logger.debug, self,
                                    ' '.join(msg),
                                    user=ig_user,
                                    last_id=ig.last_id,
                                    color_comment=reddit.display_id(comment),
                            )

                            with self.ig_queue:
                                self.ig_queue.insert(
                                        ig_user, comment, ig.last_id,
                                )

                        # the comment's author may be trying to troll the bot
                        if 404 in ig.status_codes:
                            self._increment_bad_actor(
                                    comment,
                                    comment.permalink(),
                            )

                    comment_queued = comment in self.ig_queue
                    # don't reply if any ig user was queued to be fetched
                    # (ie, don't reply with partial highlights)
                    if not comment_queued:
                        if len(ig_list) == len(ig_usernames):
                            did_reply = self._reply(comment, ig_list)

                        # don't count the reply as not attempted if we ran into
                        # either the rate-limit or server issues
                        elif not is_rate_limited:
                            reply_attempted = False
                            servererr = instagram.Instagram.has_server_error()
                            logger.id(logger.debug, self,
                                    'Skipping reply to {color_comment}:'
                                    '\nis queued? {queued};'
                                    ' rate-limit? {ratelimit};'
                                    ' server err? {servererr}'
                                    '\npermalink: {permalink}'
                                    '\nusers #{num_users}: {color}'
                                    '\n#ig_list: {num_list}',
                                    color_comment=reddit.display_id(comment),
                                    queued=('yes' if comment_queued else 'no'),
                                    ratelimit=('yes'
                                        if is_rate_limited
                                        else 'no'
                                    ),
                                    servererr=('yes' if servererr else 'no'),
                                    permalink=comment.permalink(),
                                    num_users=len(ig_usernames),
                                    color=ig_usernames,
                                    num_list=len(ig_list),
                            )

        return reply_attempted, did_reply

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
            logger.id(logger.debug, self,
                    'I already replied to {color_comment}: skipping.',
                    color_comment=reddit.display_id(comment),
            )
            return False

        replied = self.reply_history.replied_comments_for_submission(
                comment.submission
        )
        if len(replied) > self.cfg.max_replies_per_post:
            logger.id(logger.debug, self,
                    'I\'ve made too many replies (#{num}) to {color_post}:'
                    ' skipping.',
                    num=self.cfg.max_replies_per_post,
                    color_post=reddit.display_id(comment.submission),
            )
            return False

        # potentially spammy
        if comment.archived:
            logger.id(logger.debug, self,
                    '{color_comment} is too old: skipping.',
                    color_comment=reddit.display_id(comment),
            )

        by_me = self.by_me(comment)
        if by_me:
            logger.id(logger.debug, self,
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
            logger.id(logger.debug, self,
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
            logger.id(logger.debug, self,
                    'Pruned #{num_posted} usernames: {color_posted}'
                    '\n\t#{num_users}: {color_users}',
                    num_posted=len(pruned),
                    color_posted=pruned,
                    num_users=len(ig_usernames),
                    color_users=ig_usernames,
            )
        return ig_usernames

    @staticmethod
    def get_padding(num):
        # TODO: move to util or something
        padding = 0
        while num > 0:
            padding += 1
            num //= 10
        return padding if padding > 0 else 1

    def process_submission_queue(self, num=5):
        """
        Tries to process num elements in the submission_queue

        num (int, optional) - number of elements to process (halts if the queue
                is empty regardless of number of elements processed).
        """
        if not isinstance(num, int) or num < 0:
            num = 5

        try:
            for i in range(num):
                submission, mention = self.submission_queue.get_nowait()

                logger.id(logger.debug, self,
                        '[{i:>{padding}}/{num}] Processing submission'
                        ' {color_submission} (#{qnum} remaining) ...',
                        i=i+1,
                        padding=IgHighlightsBot.get_padding(num),
                        num=num,
                        color_submission=submission,
                        qnum=self.submission_queue.qsize(),
                )

                reply_attempted = True
                did_reply = False
                for comment in submission.comments.list():
                    comment_reply_attempted, comment_did_reply = \
                            self.reply(comment)

                    # AND because we want to know if the post had no replyable
                    # comments
                    reply_attempted = (
                            comment_reply_attempted and reply_attempted
                    )

                    # OR because we want to know if the bot replied at all over
                    # the entire post
                    did_reply = comment_did_reply or did_reply

                if not reply_attempted:
                    self._increment_bad_actor(mention, submission.permalink)

                if (
                        self.cfg.add_subreddit_threshold >= 0
                        and did_reply
                        and submission not in self.subreddits
                ):
                    to_add_count = self.potential_subreddits.count(submission)
                    prefixed_subreddit = reddit.prefix_subreddit(
                            submission.subreddit.display_name
                    )
                    if to_add_count + 1 > self.cfg.add_subreddit_threshold:
                        logger.id(logger.debug, self,
                                'Adding {color_subreddit} to permanent'
                                ' subreddits',
                                color_subreddit=prefixed_subreddit,
                        )

                        # add the subreddit to the permanent set of comment
                        # stream subreddits
                        with self.subreddits:
                            self.subreddits.insert(submission)
                        with self.potential_subreddits:
                            self.potential_subreddits.delete(submission)

                    else:
                        logger.id(logger.debug, self,
                                '{color_subreddit} to-add count: {num}',
                                color_subreddit=prefixed_subreddit,
                                num=to_add_count+1,
                        )
                        # increment the to-add count for this subreddit
                        with self.potential_subreddits:
                            self.potential_subreddits.insert(submission)

                self.submission_queue.task_done()

        except queue.Empty:
            pass

    def process_instagram_queue(self, num=5):
        """
        Tries to process num elements from the instagram queue (does nothing
        if instagram rate-limited).
        """
        if instagram.Instagram.is_rate_limited():
            return

        if not isinstance(num, int) or num < 0:
            num = 5

        for i in range(num):
            comment_id = self.ig_queue.get()
            if not comment_id:
                # queue empty
                break

            logger.id(logger.debug, self,
                    '[{i:>{padding}}/{num}] Processing ig queue:'
                    ' {color_comment} (#{qsize} remaining) ...',
                    i=i,
                    padding=IgHighlightsBot.get_padding(num),
                    num=num,
                    color_comment=comment_id,
                    # -1 because get() doesn't remove the element
                    qsize=self.ig_queue.size()-1,
            )

            comment = self._reddit.comment(comment_id)
            reply_attempted, did_reply = self.reply(comment)

            if did_reply:
                logger.id(logger.debug, self,
                        'Removing {color_comment} from queue ...',
                        color_comment=reddit.display_id(comment),
                )
                with self.ig_queue:
                    self.ig_queue.delete(comment)

            if instagram.Instagram.is_rate_limited():
                # no point in continuing if we're rate-limited
                break

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
                try:
                    current_subreddits = self.__current_subreddits

                except AttributeError:
                    current_subreddits = set()

                subs_from_db = self.subreddits.get_all_subreddits()
                # verify that the set of subreddits actually changed
                # (the database file could have been modified with nothing)
                diff = subs_from_db.symmetric_difference(current_subreddits)

                if bool(diff):
                    logger.id(logger.debug, self,
                            'New/missing subreddits: {color}',
                            color=diff,
                    )

                    subreddits_str = reddit.pack_subreddits(subs_from_db)
                    if subreddits_str:
                        comment_subreddits = self._reddit.subreddit(
                                subreddits_str
                        )
                        comment_stream = comment_subreddits.stream.comments(
                                pause_after=0
                        )
                        self.__cached_comment_stream = comment_stream
                        self.__current_subreddits = subs_from_db
        return comment_stream

    def run_forever(self):
        """
        Bot comment stream parsing
        """
        self.messages.start()
        self.mentions.start()

        try:
            while not self._killed:
                if self.stream:
                    # TODO: can GETs cause praw to throw a ratelimit exception?
                    for comment in self.stream:
                        if not comment:
                            break

                        self.reply(comment)

                # these should usually be empty but may cause comments to be
                # missed if they take a long time or stream contains a lot of
                # active subreddits
                self.process_submission_queue()
                self.process_instagram_queue()
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
                        exc_info=e,
                )
                raise

        finally:
            logger.id(logger.info, self,
                    'Exiting ...',
            )


__all__ = [
        'IgHighlightsBot',
]

