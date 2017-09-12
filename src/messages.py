import multiprocessing
import re

from praw.models import (
        Message,
        SubredditMessage,
)
from utillib import logger

from constants import (
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

    def __init__(self, cfg, blacklist_queue):
        self.cfg = cfg
        self.blacklist_queue = blacklist_queue

        self.__proc = multiprocessing.Process(target=self.run_forever)
        self.__proc.daemon = True

    def __str__(self):
        result = [self.__class__.__name__]
        try:
            result.append(self.__pid)
        except AttributeError:
            pass

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

        else:
            self.__pid = self.__proc.pid

    def _get_prefixed_name(self, message):
        """
        Attempts to prefix a message author's name with the appropriate prefix
        (subreddit or user)

        Returns str if lookup successful
                None otherwise (failure most likely due to account deletion)
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

        return (
                redditprefix.prefix(name, prefix)
                if bool(prefix) and bool(name)
                else None
        )

    def run_forever(self):
        reddit_obj = >>> TODO <<<
        blacklist_re = re.compile(r'^({0}|{1})$'.format(
            BLACKLIST_SUBJECT, REMOVE_BLACKLIST_SUBJECT
        ))
        messages_db = database.MessagesDatabase(self.cfg.messages_db_path)
        delay = 5 * 60

        try:
            while not self._kill.is_set():
                logger.prepend_id(logger.debug, self, 'Processing messages ...')
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
                    name = self._get_prefixed_name(message)
                    if not name:
                        logger.prepend_id(logger.debug, self,
                                'Message ({color_message}) \'{subject}\':'
                                ' could not find name! skipping ...',
                                color_message=message.id,
                                subject=subject,
                        )
                        continue

                    is_add = BLACKLIST_SUBJECT in match.group(1)
                    is_remove = REMOVE_BLACKLIST_SUBJECT in match.group(1)
                    self.blacklist_queue.put({
                        KEY_BLACKLIST_NAME: name,
                        # XXX: these are mutually exclusive but I assume it's
                        # better practice to be as explicit as possible when
                        # working asynchronously
                        KEY_BLACKLIST_ADD: is_add,
                        KEY_BLACKLIST_REMOVE: is_remove,
                    })

                logger.prepend_id(logger.debug, self,
                        'Waiting {time} ...',
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

