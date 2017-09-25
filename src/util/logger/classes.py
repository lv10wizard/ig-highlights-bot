from __future__ import print_function
from errno import EEXIST
import logging
import multiprocessing
import os
import sys
import time

from six import MAXSIZE


__DEBUG__ = False

_lock = multiprocessing.RLock()

class _Logger(logging.Logger):
    def _log(self, level, msg, args, exc_info=None, extra=None, **kwargs):
        """
        This is a copy/paste of the python2.7 logging.Logger._log method
        EXCEPT it passes extra **kwargs to makeRecord so that string.format
        can function appropriately.

        https://hg.python.org/cpython/file/2.7/Lib/logging/__init__.py#l1267
        """
        if logging._srcfile:
            #IronPython doesn't track Python frames, so findCaller raises an
            #exception on some versions of IronPython. We trap it here so that
            #IronPython can use logging.
            try:
                fn, lno, func = self.findCaller()
            except ValueError:
                fn, lno, func = "(unknown file)", 0, "(unknown function)"
        else:
            fn, lno, func = "(unknown file)", 0, "(unknown function)"
        if exc_info:
            if not isinstance(exc_info, tuple):
                exc_info = sys.exc_info()

        if msg and exc_info:
            # prepend the exception type name before the message
            exc = exc_info[1]
            if isinstance(exc, BaseException):
                try:
                    exc_type = []
                    if hasattr(exc, '__module__'):
                        exc_type.append(exc.__module__)
                    exc_type.append(exc.__class__.__name__)
                    exc_type_str = '.'.join(exc_type)
                except AttributeError as e:
                    pass
                else:
                    msg = '{0}: {1}'.format(exc_type_str, msg)

        record = self.makeRecord(
                self.name, level, fn, lno, msg, args, exc_info, func, extra,
                **kwargs
        )
        self.handle(record)

    def makeRecord(self,
            name, lvl, fn, lno, msg, args, exc_info, func=None, extra=None,
            **kwargs
    ):
        if __DEBUG__:
            print('calling custom makeRecord:')
            print('\tname:    ', name)
            print('\tlvl:     ', lvl)
            print('\tfn:      ', fn)
            print('\tlno:     ', lno)
            print('\tmsg:     ', msg)
            print('\targs:    ', args)
            print('\texc_info:', exc_info)
            print('\tfunc:    ', func)
            print('\textra:   ', extra)
            print('\tkwargs:  ', kwargs)

        record = logging.Logger.makeRecord(
                self, name, lvl, fn, lno, msg, args, exc_info, func, extra,
        )

        record.kwargs = kwargs
        if __DEBUG__:
            print('record.kwargs =', record.kwargs)
        return record

class LevelFilter(logging.Filter):
    """
    Filters LogRecords based on level

    https://stackoverflow.com/a/1383365
    """
    def __init__(self, min_level, max_level=MAXSIZE):
        self.min_level = min_level
        self.max_level = max_level

    def filter(self, record):
        return self.min_level <= record.levelno <= self.max_level

class ProcessStreamHandler(logging.StreamHandler):
    """
    multiprocessing-safe stream logging handler
    """
    def emit(self, *args, **kwargs):
        with _lock:
            logging.StreamHandler.emit(self, *args, **kwargs)

class ProcessFileHandler(logging.FileHandler):
    """
    multiprocessing-safe file logging handler
    """

    @staticmethod
    def mkdirs(path):
        # https://stackoverflow.com/a/20667049
        try:
            os.makedirs(path, exist_ok=True) # python > 3.2
        except TypeError: # python <= 3.2
            try:
                os.makedirs(path)
            except OSError as e: # python > 2.5
                if e.errno == EEXIST and os.path.isdir(path):
                    pass
                else:
                    raise

    def __init__(self, root_dir, mode='a', encoding=None, delay=False):
        # structure the logging directory by date
        # eg. root/2017/09/24.131142.log
        path = os.path.join(root_dir, time.strftime('%Y'), time.strftime('%m'))
        if not delay:
            ProcessFileHandler.mkdirs(path)
        else:
            # set the path so that the creating the directories is delayed until
            # the first emit call
            self.__path = path
        filename = os.path.join(path, time.strftime('%d.%H%M%S.log'))

        logging.FileHandler.__init__(self, filename, mode, encoding, delay)

    def emit(self, *args, **kwargs):
        try:
            ProcessFileHandler.mkdirs(self.__path)
        except AttributeError:
            pass
        else:
            del self.__path

        with _lock:
            logging.FileHandler.emit(self, *args, **kwargs)


__all__ = [
        'LevelFilter',
        'ProcessStreamHandler',
        'ProcessFileHandler',
]

