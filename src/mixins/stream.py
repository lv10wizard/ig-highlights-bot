import abc
from errno import ECONNRESET
import time

from six import add_metaclass
from prawcore.exceptions import (
        Redirect,
        RequestException,
        ResponseException,
        ServerError,
)
from praw.models import util as praw_util

from .redditinstance import RedditInstanceMixin
from src import reddit
from src.database import SubredditsDatabase
from src.util import (
        logger,
        requestor,
)


class StreamMixin(RedditInstanceMixin):
    """
    Provides Reddit.stream_generator fetching through the .stream property.
    This mixin handles delaying the next fetch when either a RequestException or
    ServerError is thrown (internet hiccup, reddit down).
    """

    @property
    def _stream_method(self):
        """
        The stream method (eg. inbox.messages) used in the default _stream
        functionality.
        """
        # don't force child classes to define this if they override _stream
        # (this does mean that child classes that do rely on the default _stream
        #  behavior will throw a run-time error rather than a "compile"-time
        #  one)
        raise NotImplementedError('_stream_method')

    @property
    def _stream(self):
        """
        The Reddit stream_generator to fetch data from. This should be cached.
        """
        try:
            return self._cached_stream
        except AttributeError:
            self._cached_stream = praw_util.stream_generator(
                    self._stream_method,
                    pause_after=self._pause_after,
            )
            return self._cached_stream

    @property
    def _pause_after(self):
        """
        This is passed to pause_after argument of stream_generator
        """
        return 0

    def __sleep(self, delay):
        if self.__is_alive:
            logger.id(logger.info, self,
                    'Waiting {time} ...',
                    time=delay,
            )
            try:
                self._killed.wait(delay)
            except AttributeError:
                time.sleep(delay)

        else:
            logger.id(logger.debug, self,
                    'Skipping sleep ({time}): killed!',
                    time=delay,
            )

    @property
    def __delay(self):
        """
        Cached, exponentially increasing delay
        """
        try:
            delay = self.__cached_delay
        except AttributeError:
            delay = 1
        delay = requestor.choose_delay(delay)
        self.__cached_delay = delay
        return delay

    def __reset_delay(self):
        new_delay = 1
        try:
            if self.__cached_delay > new_delay:
                logger.id(logger.debug, self,
                        'Resetting delay {old} -> {new}',
                        old=self.__cached_delay,
                        new=new_delay,
                )
                self.__cached_delay = new_delay
        except AttributeError:
            pass

    @property
    def __is_alive(self):
        """
        Returns True if the stream should continue running
        """
        try:
            return not (
                    # check the _killed flag in case it is a bool
                    self._killed and (
                        # check the _killed.is_set method in case it is an Event
                        hasattr(self._killed, 'is_set')
                        and self._killed.is_set()
                    )
            )
        except AttributeError:
            return True

    @property
    def stream(self):
        while self.__is_alive:
            try:
                for thing in self._stream:
                    yield thing

            except (RequestException, ResponseException, ServerError) as e:
                # retry all RequestExceptions
                is_retryable = isinstance(e, RequestException)

#                 if hasattr(e, 'original_exception'):
#                     # RequestException
#                     try:
#                         is_retryable = e.original_exception.errno == ECONNRESET
#                     except AttributeError:
#                         is_retryable = False
                if not is_retryable and hasattr(e, 'response'):
                    try:
                        status_code = e.response.status_code
                    except AttributeError:
                        status_code = -1
                    is_retryable = status_code // 100 == 5

                logger.id(logger.info, self,
                        'Failed to fetch stream element!{retry}',
                        retry=(' Retrying ...' if is_retryable else ''),
                        exc_info=True,
                )
                if is_retryable:
                    self.__sleep(self.__delay)
                    # XXX: have to restart the stream because the generator
                    # will no longer generate elements
                    logger.id(logger.info, self, 'Restarting stream ...')
                    try:
                        del self._cached_stream
                    except AttributeError:
                        # this shouldn't happen
                        pass
                else:
                    raise
            else:
                self.__reset_delay()

@add_metaclass(abc.ABCMeta)
class _SubredditsStreamMixin(StreamMixin):
    """
    Abstract base class providing functionality for comments/submissions streams
    for subreddits
    """

    def __init__(self, *args, **kwargs):
        StreamMixin.__init__(self, *args, **kwargs)
        self.subreddits = SubredditsDatabase(do_seed=True)

    @abc.abstractproperty
    def _stream_type(self):
        """ Returns the stream type string: 'comments' or 'submissions' """

    @property
    def _stream(self):
        """
        Cached subreddits.<type> stream. This will update the stream generator
        if the subreddits database has been modified.

        Note: renewing the stream will cause some things (comments/submissions)
        to be re-parsed.
        """
        try:
            the_stream = self._cached_stream
        except AttributeError:
            the_stream = None

        if the_stream is None or self.subreddits.is_dirty:
            with self.subreddits.updating():
                logger.id(logger.info, self, 'Updating subreddits ...')

                try:
                    current_subreddits = self.__current_subreddits
                except AttributeError:
                    current_subreddits = set()

                subs_from_db = self.subreddits.get_all_subreddits()
                # verify that the set of subreddits actually changed
                # (the database file could have been modified with nothing)
                diff = subs_from_db.symmetric_difference(current_subreddits)

                # force an update regardless of the diff if there is no cached
                # stream (this may happen if the previously cached stream was
                # discarded due to a praw GET error)
                if bool(diff) or the_stream is None:
                    new = subs_from_db - current_subreddits
                    if new:
                        logger.id(logger.info, self,
                                'New subreddits: {color}',
                                color=new,
                        )
                    removed = current_subreddits - subs_from_db
                    if removed:
                        logger.id(logger.info, self,
                                'Removed subreddits: {color}',
                                color=removed,
                        )
                    if new or removed:
                        # if the set of subreddits does not receive many
                        # comments/submissions, then the stream may contain
                        # duplicates
                        logger.id(logger.info, self,
                                'Re-initializing {type} stream (some {type}'
                                ' may have been processed before) ...',
                                type=self._stream_type,
                        )

                    subreddits_str = reddit.pack_subreddits(subs_from_db)
                    logger.id(logger.debug, self,
                            'subreddit string:\n\t{subreddits_str}',
                            subreddits_str=subreddits_str,
                    )
                    if subreddits_str:
                        subreddits_obj = self._reddit.subreddit(
                                subreddits_str
                        )
                        stream_func = getattr(
                                subreddits_obj.stream, self._stream_type
                        )
                        the_stream = stream_func(pause_after=self._pause_after)
                        self._cached_stream = the_stream
                        self.__current_subreddits = subs_from_db

                else:
                    msg = ['No']
                    if the_stream is not None:
                        msg.append('new')
                    msg.append('subreddits!')
                    logger.id(logger.info, self, ' '.join(msg))

        return the_stream

    @property
    def stream(self):
        try:
            return StreamMixin.stream.fget(self)

        except Redirect as e:
            import re

            if re.search(r'/subreddits/search', e.message):
                try:
                    subs = self.__current_subreddits
                except AttributeError:
                    # this shouldn't happen
                    logger.id(logger.debug, self, 'No current subreddits ...?')
                    subs = set()

                logger.id(logger.critical, self,
                        'One or more non-existant subreddits: {color}',
                        color=subs,
                )
                raise

class SubredditsCommentStreamMixin(_SubredditsStreamMixin):
    """
    Provides subreddits' comment stream through the .stream property
    """
    @property
    def _stream_type(self):
        return 'comments'

class SubredditsSubmissionsStreamMixin(_SubredditsStreamMixin):
    """
    Provides subreddits' submissions stream through the .stream property
    """
    @property
    def _stream_type(self):
        return 'submissions'


__all__ = [
        'StreamMixin',
        'SubredditsCommentStreamMixin',
        'SubredditsSubmissionsStreamMixin',
]

