import abc
import multiprocessing

from utillib import logger


class ProcessMixin(object):
    """
    Provides multiprocessing functionality through the abstract method
    _run_forever
    """

    __metaclass__ = abc.ABCMeta

    def __init__(self, daemon=True):
        self.__proc = multiprocessing.Process(target=self.run_forever)
        self.__proc.daemon = daemon

    def __str__(self):
        result = filter(None, [
            self.__class__.__name__,
            self.__proc.pid,
        ])
        return ':'.join(result)

    @abc.abstractmethod
    def _run_forever(self):
        pass

    @property
    def is_alive(self):
        return self.__proc.is_alive()

    def kill(self, block=False):
        """
        Sets the kill flag for the process. Blocks if block==True.
        """
        if hasattr(self, '_killed') and hasattr(self._killed, 'set'):
            logger.prepend_id(logger.debug, self, 'Setting kill flag ...')
            self._killed.set()
            if block:
                self.join()

        else:
            logger.prepend_id(logger.debug, self,
                    'Failed to set kill flag (is alive? {status})',
                    status=('yes' if self.is_alive else 'no'),
            )

    def join(self):
        return self.__proc.join()

    def start(self):
        logger.prepend_id(logger.debug, self, 'Starting process ...')
        if not hasattr(self, '_killed'):
            self._killed = multiprocessing.Event()

        try:
            self.__proc.start()

        except AssertionError:
            try:
                self.__multi_start_count += 1
            except (AttributeError, TypeError):
                # start at 2 since this should be the second time start() was
                # called
                self.__multi_start_count = 2
            logger.prepend_id(logger.debug, self,
                    'Attempted to start process again (#{num})!',
                    num=self.__multi_start_count,
            )

    def run_forever(self):
        """
        The process's target function (wrapper for _run_forever)
        """
        try:
            self._run_forever()

        finally:
            logger.prepend_id(logger.info, self,
                    'Exiting ...',
            )


__all__ = [
        'ProcessMixin',
]

