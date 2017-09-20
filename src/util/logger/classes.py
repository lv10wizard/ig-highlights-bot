from __future__ import print_function
import logging
import multiprocessing
import sys


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

        if msg is None:
            msg = ''
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
    def __init__(self, min_level, max_level=sys.maxint):
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
    def emit(self, *args, **kwargs):
        with _lock:
            logging.FileHandler.emit(self, *args, **kwargs)


__all__ = [
        'LevelFilter',
        'ProcessStreamHandler',
        'ProcessFileHandler',
]

