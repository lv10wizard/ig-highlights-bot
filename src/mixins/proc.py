import abc
import multiprocessing
import os

from six import add_metaclass

from constants import RUNTIME_ROOT_DIR
from src.config import resolve_path
from src.util import (
        choose_filename,
        logger,
        mkdirs,
)


# ----------------------------------------------------------------------
# TODO: move these somewhere else (do they belong here?)
def write_pid(name, pid=None, increment=False):
    """
    Writes the current pid to RUNTIME_ROOT_DIR/name.pid

    Returns the full path to the pid file
    """
    if increment:
        path = choose_filename(RUNTIME_ROOT_DIR, name, 'pid')
    else:
        path = os.path.join(
                resolve_path(RUNTIME_ROOT_DIR),
                '{0}.pid'.format(name),
        )

    try:
        mkdirs(RUNTIME_ROOT_DIR)
    except OSError:
        logger.critical('Failed to write pid to \'{path}\'',
                path=path,
        )
        raise

    if not pid:
        pid = os.getpid()
    pid = str(pid)

    logger.debug('Writing pid={pid} to \'{path}\' ...',
            pid=pid,
            path=path,
    )
    try:
        with open(path, 'w') as fd:
            fd.write(pid)
    except (IOError, OSError):
        logger.critical('Failed to write pid to \'{path}\'',
                path=path,
        )
        raise

    return path

def get_pid_file(name):
    """
    Returns the full path of the existing pid if it exists (None otherwise)
    """
    path = os.path.join(resolve_path(RUNTIME_ROOT_DIR), '{0}.pid'.format(name))
    return path if os.path.exists(path) else None
# ----------------------------------------------------------------------

@add_metaclass(abc.ABCMeta)
class RunForeverMixin(object):
    """
    Provides long-running functionality through its run_forever method which
    calls the abstractmethod _run_forever.

    This class handles writing the process's pid to file and logging uncaught
    exceptions and exit.
    """

    @abc.abstractmethod
    def _run_forever(self):
        """
        The function that actually does the run_forever work. This should
        be an infinite-ish loop.
        """

    def run_forever(self):
        """
        The process's target function (wrapper for _run_forever)
        """
        # ensure there is only one instance of this class running across the
        # system
        # TODO? move to a separate mixin? (pid stuff may not belong here)
        pid_file = get_pid_file(self.__class__.__name__)
        if pid_file:
            pid = None
            try:
                with open(pid_file, 'r') as fd:
                    pid = pid_file.read()
            except (IOError, OSError):
                logger.id(logger.debug, self,
                        'Failed to read pid @ \'{path}\'',
                        path=pid_file,
                        exc_info=True,
                )

            msg = ['\'{path}\' exists! is another bot running?']
            if pid:
                msg.append('(pid={pid})')
            logger.id(logger.info, self,
                    ' '.join(msg),
                    path=pid_file,
                    pid=pid,
            )
            return

        pid_file = write_pid(self.__class__.__name__)

        try:
            self._run_forever()

        except:
            logger.id(logger.exception, self, 'An uncaught exception occured!')
            raise

        finally:
            logger.id(logger.debug, self,
                    'Removing pid file \'{path}\' ...',
                    path=pid_file,
            )
            try:
                os.remove(pid_file)
            except (IOError, OSError):
                logger.id(logger.warn, self,
                        'Failed to remove pid file \'{path}\'!',
                        path=pid_file,
                        exc_info=True,
                )

            logger.id(logger.info, self, 'Exiting ...')

@add_metaclass(abc.ABCMeta)
class ProcessMixin(RunForeverMixin):
    """
    Provides multiprocessing functionality through the abstract method
    _run_forever
    """

    def __init__(self, daemon=True):
        self.__proc = multiprocessing.Process(target=self.run_forever)
        self.__proc.daemon = daemon

    def __str__(self):
        result = [self.__class__.__name__]
        if self.__proc.pid:
            result.append(self.__proc.pid)
        return ':'.join(result)

    @property
    def is_alive(self):
        return self.__proc.is_alive()

    def kill(self, block=False):
        """
        Sets the kill flag for the process. Blocks if block==True.
        """
        if hasattr(self, '_killed') and hasattr(self._killed, 'set'):
            logger.id(logger.debug, self, 'Setting kill flag ...')
            self._killed.set()
            if block:
                self.join()

        else:
            logger.id(logger.debug, self,
                    'Failed to set kill flag (is alive? {yesno_status})',
                    yesno_status=self.is_alive,
            )

    def join(self):
        return self.__proc.join()

    def start(self):
        logger.id(logger.debug, self, 'Starting process ...')
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
            logger.id(logger.debug, self,
                    'Attempted to start process again (#{num})!',
                    num=self.__multi_start_count,
            )


__all__ = [
        'write_pid',
        'get_pid_file',
        'ProcessMixin',
        'RunForeverMixin',
]

