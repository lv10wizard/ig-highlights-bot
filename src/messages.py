import inspect
import os
import re
import time

from praw.models import (
        Message,
        SubredditMessage,
)
from constants import (
        BLACKLIST_SUBJECT,
        REMOVE_BLACKLIST_SUBJECT,
)
from src import (
        database,
        reddit,
)
from src.mixins import (
        ProcessMixin,
        StreamMixin,
)
from src.util import logger


class Messages(ProcessMixin, StreamMixin):
    """
    Inbox message parser
    """

    def __init__(self, cfg, rate_limited, rate_limit_time, blacklist):
        ProcessMixin.__init__(self)
        StreamMixin.__init__(self, cfg, rate_limited, rate_limit_time)

        self.blacklist = blacklist

    def _get_prefix_name(self, message):
        """
        Attempts to prefix a message author's name with the appropriate prefix
        (subreddit or user)

        Returns (prefix, name) if lookup successful
                (None, None) otherwise (failure most likely due to account
                    deletion)
        """
        prefix = None
        name = None

        # check SubredditMessage first since it is a child of Message
        if isinstance(message, SubredditMessage):
            try:
                # XXX: specifically lookup subreddit.display_name rather than
                # subreddit_name_prefixed in case the subreddit is a user
                # profile (the latter returns 'u/username')
                name = message.subreddit.display_name
            except AttributeError as e:
                # not sure how this would happen..
                # maybe subreddit went private? can subreddits be deleted?
                logger.id(logger.warn, self,
                        'Failed to get message\'s subreddit display_name'
                        ' ({color_message})',
                        color_message=message.id,
                        exc_info=True,
                )
            else:
                prefix = PREFIX_SUBREDDIT

        elif isinstance(message, Message):
            try:
                name = message.author.name
            except AttributeError as e:
                # probably account deletion (possibly suspension)
                logger.id(logger.warn, self,
                        'Failed to get message\'s author name'
                        ' ({color_message})',
                        color_message=message.id,
                        exc_info=True,
                )
            else:
                prefix = PREFIX_USER

        else:
            logger.id(logger.debug, self,
                    'Unknown message type={mtype}. ignoring ...',
                    mtype=type(message),
            )

        return prefix, name

    def _format_reply(self, message, subject, name, prefix):
        """
        Formats a reply for a successfully processed message
        """
        reply_text = None
        you = None

        prefixed_name = reddit.prefix(name, prefix)
        if reddit.is_subreddit_prefix(prefix):
            you = ' '.join(['posts/comments in', prefixed_name])

        elif reddit.is_user_prefix(prefix):
            you = ''.join(['you (', prefixed_name, ')'])

        if not you:
            # could fail if prefix is unhandled (new reddit prefix
            # or changed prefixes)
            logger.id(logger.debug, self,
                    'Could not format appropriate \'you\' to'
                    ' reply to message ({color_message}) with!'
                    '\nprefix = \'{p}\'\tname = \'{n}\'',
                    color_message=message.id,
                    p=prefix,
                    n=name,
            )

        else:
            if self._is_add(subject):
                reply_text = 'I should no longer reply to {0}'.format(you)

            elif self._is_remove(subject):
                reply_text = 'I should start replying to {0} again'.format(you)

            else:
                logger.id(logger.debug, self,
                        'Could not format appropriate reply: unhandled subject'
                        ' \'{subject}\'!',
                        subject=subject,
                )

        return reply_text

    def _debug_pm(self, message, name, prefix, regex):
        """
        Constructs a pm with some debugging information in the event that
        something goes catstrophically wrong. (This is mainly in case logs are
        not being closely monitored.)

        Returns tuple(str, str)
        """
        prefixed_name = reddit.prefix(name, prefix)
        LINE_SEP = '---'
        TIME_FMT = '%Y/%m/%d @ %H:%M:%S'
        subject = 'Unhandled message from \'{name}\''.format(name=prefixed_name)
        body = '\n\n'.join([
            '{0} @ {1}'.format(
                os.path.basename(__file__),
                inspect.currentframe().f_lineno,
            ),
            LINE_SEP,
            'subject regex: `{0}`'.format(regex.pattern),
            'processed at: `{0}` (`{1}`)'.format(
                time.strftime(TIME_FMT),
                time.time(),
            ),
            LINE_SEP,
            # TODO? trim very long subjects (may cause message body
            # to exceed character limit)
            'message subject: `{0}`'.format(message.subject),
            'message from: `{0}`'.format(prefixed_name),
            'sent at: `{0}` (`{1}`)'.format(
                time.strftime(
                    TIME_FMT,
                    time.localtime(message.created_utc),
                ),
                message.created_utc,
            ),
            # LINE_SEP,
            # '`message body:` {0}'.format(message.body),
        ])
        return subject, body

    def _is_add(self, subject):
        return BLACKLIST_SUBJECT in subject

    def _is_remove(self, subject):
        return REMOVE_BLACKLIST_SUBJECT in subject

    @property
    def _stream_method(self):
        return self._reddit.inbox.messages

    def _run_forever(self):
        blacklist_re = re.compile(r'^({0}|{1})$'.format(
            BLACKLIST_SUBJECT,
            REMOVE_BLACKLIST_SUBJECT,
        ))
        messages_db = database.MessagesDatabase()
        # XXX: a manual delay is used instead of relying on praw's stream
        # delay so that external shutdown events can be received in a timely
        # fashion.
        delay = 15 # too long?

        while not self._killed.is_set():
            logger.id(logger.debug, self, 'Processing messages ...')
            for message in self.stream:
                if message is None or self._killed.is_set():
                    break

                # don't rely on read/unread flag in case someone logs in
                # to the bot account and reads all the messages
                # assumption: inbox.messages() fetches newest -> oldest
                elif messages_db.has_seen(message):
                    logger.id(logger.debug, self,
                            'I\'ve already read {color_message}!'
                            ' (\'{subject}\' from {color_from})',
                            color_message=reddit.display_fullname(message),
                            subject=message.subject,
                            color_from=reddit.author(message),
                    )
                    break

                # blindly mark messages as seen even if processing fails.
                # this prevents random / spam messages from being processed
                # every time; however, it also prevents failed messages from
                # being retried.
                try:
                    with messages_db:
                        messages_db.insert(message)
                except database.UniqueConstraintFailed:
                    # this means there is a bug in has_seen
                    logger.id(logger.warn, self,
                            'Attempted to process duplicate message:'
                            ' {color_message} from {color_from}!',
                            color_message=reddit.display_fullname(message),
                            color_from=reddit.author(message),
                            exc_info=True,
                    )
                    break

                # ignore comments, though I don't think it is possible that
                # any message in the messages() inbox can be a comment.
                if message.was_comment:
                    continue

                subject = message.subject.strip()
                match = blacklist_re.search(subject)
                # ignore random messages
                if not match:
                    logger.id(logger.debug, self,
                            'Ignoring {color_message}: \'{subject}\'',
                            color_message=message.id,
                            subject=subject,
                    )
                    continue

                # need to blacklist a subreddit or user
                prefix, name = self._get_prefix_name(message)
                if not name:
                    logger.id(logger.debug, self,
                            'Message ({color_message}) \'{subject}\':'
                            ' could not find name! skipping ...',
                            color_message=message.id,
                            subject=subject,
                    )
                    continue

                do_reply = False
                if self._is_add(match.group(1)):
                    do_reply = self.blacklist.add(name, prefix)

                elif self._is_remove(match.group(1)):
                    do_reply = self.blacklist.remove(name, prefix)

                else:
                    # subject regex updated but no code to handle ...
                    # XXX: flagging the message as unseen may not
                    # necessarily do anything if it does not remain the
                    # newest message

                    logger.id(logger.debug, self,
                            'Unhandled subject: \'{subject}\'!'
                            '\nmatch: \'{match}\'',
                            subject=subject,
                            match=match.group(1),
                    )

                    # send a pm to the maintainer in case logs aren't being
                    # monitored closely
                    pm_subject, pm_body = self._debug_pm(
                            message, name, prefix, blacklist_re,
                    )
                    self._reddit.send_debug_pm(
                            subject=pm_subject,
                            body=pm_body,
                    )

                if do_reply:
                    reply_text = self._format_reply(
                            message=message,
                            subject=match.group(1),
                            name=name,
                            prefix=prefix,
                    )
                    if reply_text:
                        self._reddit.do_reply(message, reply_text, self._killed)

            if not self._killed.is_set():
                logger.id(logger.debug, self,
                        'Waiting {time} before checking messages again ...',
                        time=delay,
                )
            self._killed.wait(delay)

        if self._killed.is_set():
            logger.id(logger.debug, self, 'Killed!')


__all__ = [
        'Message',
]

