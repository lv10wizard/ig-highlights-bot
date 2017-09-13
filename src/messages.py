import inspect
import os
import multiprocessing
import re
import time

from praw.models import (
        Message,
        SubredditMessage,
)
from utillib import logger

from constants import (
        AUTHOR,
        BLACKLIST_SUBJECT,
        REMOVE_BLACKLIST_SUBJECT,
        KEY_BLACKLIST_NAME,
        KEY_BLACKLIST_ADD,
        KEY_BLACKLIST_REMOVE,
)
from src import (
        database,
        redditprefix,
)


class Messages(object):
    """
    Inbox message parser
    """

    def __init__(self, cfg, blacklist):
        self.cfg = cfg
        self.blacklist = blacklist

        self.__proc = multiprocessing.Process(target=self.run_forever)
        self.__proc.daemon = True

    def __str__(self):
        result = filter(None, [
                self.__class__.__name__,
                self.__proc.pid,
        ])

        return ':'.join(result)

    @property
    def is_alive(self):
        return self.__proc.is_alive()

    def kill(self, block=True):
        """
        Sets the kill flag for the messages process. Will wait for the process
        to finish if block == True
        """
        if hasattr(self, '_kill') and hasattr(self._kill, 'set'):
            logger.prepend_id(logger.debug, self, 'Setting kill flag ...')
            self._kill.set()
            if block:
                self.__proc.join()

        else:
            logger.prepend_id(logger.debug, self,
                    'Failed to set kill flag (is alive? {status})',
                    status=('yes' if self.is_alive else 'no'),
            )

    def start(self):
        logger.prepend_id(logger.debug, self, 'Starting process ...')
        if not hasattr(self, '_kill'):
            self._kill = multiprocessing.Event()
        try:
            self.__proc.start()

        except AssertionError:
            if not hasattr(self, '_multi_start_count'):
                self._multi_start_count = 1 # start at 2
            self._multi_start_count += 1
            logger.prepend_id(logger.debug, self,
                    'Attempted to start process again (#{num})!',
                    num=self._multi_start_count,
            )

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
                logger.prepend_id(logger.error, self,
                        'Failed to get message\'s subreddit display_name'
                        ' ({color_message})', e,
                        color_message=message.id,
                )
            else:
                prefix = PREFIX_SUBREDDIT

        elif isinstance(message, Message):
            try:
                name = message.author.name
            except AttributeError as e:
                # probably account deletion (possibly suspension)
                logger.prepend_id(logger.error, self,
                        'Failed to get message\'s author name'
                        ' ({color_message})', e,
                        color_message=message.id,
                )
            else:
                prefix = PREFIX_USER

        else:
            logger.prepend_id(logger.debug, self,
                    'Unknown message type={mtype}. ignoring ...',
                    mtype=type(message),
            )

        return prefix, name

    def _reply(self, message, reply_text):
        """
        Replies to the message with the reply_text
        """
        if not (isinstance(reply_text, basestring) and reply_text):
            logger.prepend_id(logger.debug, self,
                    'Cannot reply to message \'{mid}\':'
                    ' bad reply_text, string expected got \'{type}\''
                    ' (\'{text}\')',
                    mid=message.id,
                    type=type(reply_text),
                    text=reply_text,
            )
            return

        try:
            message.reply(reply_text)

        except praw.exceptions.APIException as e:
            pass # TODO: handle api exception function

    def _format_reply(self, message, subject, name, prefix):
        """
        Formats a reply for a successfully processed message
        """
        reply_text = None
        you = None

        prefixed_name = redditprefix.prefix(name, prefix)
        if redditprefix.is_subreddit_prefix(prefix):
            you = ' '.join(['posts/comments in', prefixed_name])

        elif redditprefix.is_user_prefix(prefix):
            you = ''.join(['you (', prefixed_name, ')'])

        if not you:
            # could fail if prefix is unhandled (new reddit prefix
            # or changed prefixes)
            logger.prepend_id(logger.debug, self,
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
                logger.prepend_id(logger.debug, self,
                        'Could not format appropriate reply: unhandled subject'
                        ' \'{subject}\'!',
                        subject=subject,
                )

        return reply_text

    def _send_debug_pm(self, reddit_obj, message, name, prefix, regex):
        """
        Sends a pm with some debugging information in the event that something
        goes catstrophically wrong. (This is mainly in case logs are not being
        closely monitored.)
        """
        if not hasattr(self, '_maintainer'):
            self._maintainer = reddit_obj.redditor(AUTHOR)

        prefixed_name = redditprefix.prefix(name, prefix)
        LINE_SEP = '---'
        TIME_FMT = '%Y/%m/%d @ %H:%M:%S'
        try:
            self._maintainer.message(
                    'Unhandled message from \'{name}\''.format(
                        name=prefixed_name,
                    ),

                    '\n\n'.join([
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
            )

        except Exception as e:
            logger.prepend_id(logger.error, self,
                    'Failed to send debugging pm to \'{color_author}\'!', e,
                    color_author=self._maintainer.name,
            )

    def _is_add(self, subject):
        return BLACKLIST_SUBJECT in subject

    def _is_remove(self, subject):
        return REMOVE_BLACKLIST_SUBJECT in subject

    def run_forever(self):
        reddit_obj = >>> TODO <<<
        blacklist_re = re.compile(r'^({0}|{1})$'.format(
            BLACKLIST_SUBJECT,
            REMOVE_BLACKLIST_SUBJECT,
        ))
        messages_db = database.MessagesDatabase(self.cfg.messages_db_path)
        delay = 5 * 60

        try:
            while not self._kill.is_set():
                logger.prepend_id(logger.debug, self, 'Processing messages ...')
                # pull the default number of messages since processing halts
                # upon seeing the first already-processed message
                # assumption: the default number of messages incurs only a
                # single hit to reddit
                for message in reddit_obj.inbox.messages():
                    # don't rely on read/unread flag in case someone logs in
                    # to the bot account and reads all the messages
                    # assumption: inbox.messages() fetches newest -> oldest
                    if messages_db.has_seen(message):
                        logger.prepend_id(logger.debug, self,
                                'I\'ve already read {color_message}!'
                                ' (\'{subject}\' from {color_from})',
                                color_message=message.fullname,
                                subject=message.subject,
                                color_from=(
                                    message.author.name
                                    if bool(message.author)
                                    else message.subreddit.display_name
                                ),
                        )
                        break

                    # blindly mark messages as seen even if processing fails.
                    # this prevents random / spam messages from being processed
                    # every time; however, it also prevents failed messages from
                    # being retried.
                    messages_db.insert(message)

                    # ignore comments, though I don't think it is possible that
                    # any message in the messages() inbox can be a comment.
                    if message.was_comment:
                        continue

                    subject = message.subject.strip()
                    match = blacklist_re.search(subject)
                    # ignore random messages
                    if not match:
                        logger.prepend_id(logger.debug, self,
                                'Ignoring {color_message}: \'{subject}\'',
                                color_message=message.id,
                                subject=subject,
                        )
                        continue

                    # need to blacklist a subreddit or user
                    prefix, name = self._get_prefix_name(message)
                    if not name:
                        logger.prepend_id(logger.debug, self,
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

                        logger.prepend_id(logger.debug, self,
                                'Unhandled subject: \'{subject}\'!'
                                '\nmatch: \'{match}\'',
                                subject=subject,
                                match=match.group(1),
                        )

                        # send a pm to the maintainer in case logs aren't being
                        # monitored closely
                        self._send_debug_pm(
                                reddit_obj=reddit_obj,
                                subject=subject,
                                name=name,
                                prefix=prefix,
                                regex=blacklist_re,
                        )

                    if do_reply:
                        reply_text = self._format_reply(
                                message=message,
                                subject=match.group(1),
                                name=name,
                                prefix=prefix,
                        )
                        if reply_text:
                            self._reply(message, reply_text)

                logger.prepend_id(logger.debug, self,
                        'Waiting {time} before checking messages again ...',
                        time=delay,
                )
                self._kill.wait(delay)

        except Exception as e:
            # TODO? only catch praw errors
            logger.prepend_id(logger.error, self,
                    'Something went wrong! Message processing terminated.',
            )


__all__ = [
        'Message',
]

