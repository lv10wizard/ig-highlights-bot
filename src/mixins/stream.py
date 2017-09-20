import abc

from prawcore.exceptions import (
        RequestException,
        ServerError,
)
from praw.models import util as praw_util

from src import reddit
from src.util import (
        logger,
        requestor,
)


class StreamMixin(object):
    """
    Provides Reddit.stream_generator fetching through the .stream property.
    This mixin handles delaying the next fetch when either a RequestException or
    ServerError is thrown (internet hiccup, reddit down).
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, cfg):
        self.cfg = cfg
        self._reddit = reddit.Reddit(cfg)

    @abc.abstractproperty
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

    @abc.abstractproperty
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

    @abc.abstractproperty
    def _pause_after(self):
        """
        This is passed to pause_after argument of stream_generator
        """
        return 0

    @abc.abstractproperty
    def _loop_condition(self):
        """
        This should return True to continue looping; False to stop.
        """
        if hasattr(self, '_killed'):
            try:
                return not self._killed.is_set()
            except AttributeError:
                return self._killed
        else:
            raise NotImplementedError('_loop_condition')

    def __sleep(self, delay):
        logger.id(logger.debug, self,
                'Waiting {time} ...',
                time=delay,
        )
        try:
            self._killed.wait(delay)
        except AttributeError:
            time.sleep(delay)

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
    def stream(self):
        while True:
            if not self._loop_condition:
                break

            try:
                for thing in self._stream:
                    yield thing
            except (RequestException, ServerError) as e:
                logger.id(logger.exception, self,
                        'Failed to fetch stream element!',
                        exc_info=e,
                )
                self.__sleep(self.__delay)
            else:
                self.__reset_delay()


__all__ = [
        'StreamMixin',
]

