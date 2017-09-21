from __future__ import print_function
import inspect
import logging
import sys

from src.util.logger.classes import (
        LevelFilter,
        ProcessStreamHandler,
)
from src.util.logger.formatter import Formatter


ROOT = '__logger_ROOT__'
# "root" _Logger instance
# (not actually the RootLogger instance but a child of it)
__ROOT_LOGGER = None

def _module_name():
    """
    Returns the first non-logger module name in the stack (ie, returns the
    calling module's name)
            or None if eg. called from interpreter
    """
    name = None
    module = None
    stack = inspect.stack()
    while stack and not module:
        frame = stack.pop(0)
        module = inspect.getmodule(frame[0])
        if module and module.__name__ == __name__:
            # not the calling module; keep looking
            module = None
    if module:
        name = module.__name__
    return name

def _initialize_root_logger():
    """
    Initializes the custom root logger so that the _Logger class is used instead
    of the bulit-in logging.RootLogger.
    """
    global __ROOT_LOGGER

    if not __ROOT_LOGGER:
        root = logging.getLogger()
        # use a direct child of the root logger as our "root" logger so that
        # it is an instance of _Logger (ie, so that it behaves in an expected
        # way)
        logger = root.getChild(ROOT)
        logger.setLevel(logging.DEBUG)

        # set some default logging variables if we're in the interpreter
        # https://stackoverflow.com/a/2356427
        if hasattr(sys, 'ps1') and hasattr(sys, 'ps2') and sys.ps1 and sys.ps2:
            # log DEBUG -> WARNING to stdout; ERROR+ to stderr
            stdout_filter = LevelFilter(logging.DEBUG, logging.WARNING)
            stderr_filter = LevelFilter(logging.ERROR)

            formatter = Formatter(fmt=Formatter.FORMAT_NO_DATE)
            stdout_handler = ProcessStreamHandler(stream=sys.stdout)
            stdout_handler.addFilter(stdout_filter)
            stdout_handler.setFormatter(formatter)

            stderr_handler = ProcessStreamHandler(stream=sys.stderr)
            stderr_handler.addFilter(stderr_filter)
            stderr_handler.setFormatter(formatter)

            logger.addHandler(stdout_handler)
            logger.addHandler(stderr_handler)

        __ROOT_LOGGER = logger

def _get(name=None):
    """
    Gets the logger for {name}. If {name} is None, then returns the calling
    module's logger (ie, module.__name__). To get the root logger,
    `logger.ROOT` should be used.

    This should not be called directly from outside of the logger module.
    """
    _initialize_root_logger()

    if name:
        return __ROOT_LOGGER.getChild(name)
    return __ROOT_LOGGER

def debug(msg=None, *args, **kwargs):
    _get(_module_name()).debug(msg, *args, **kwargs)

def info(msg=None, *args, **kwargs):
    _get(_module_name()).info(msg, *args, **kwargs)

def warn(msg=None, *args, **kwargs):
    _get(_module_name()).warn(msg, *args, **kwargs)

def error(msg=None, *args, **kwargs):
    _get(_module_name()).error(msg, *args, **kwargs)

def critical(msg=None, *args, **kwargs):
    _get(_module_name()).critical(msg, *args, **kwargs)

def exception(msg=None, *args, **kwargs):
    _get(_module_name()).exception(msg, *args, **kwargs)
    # log an empty line to help highlight exceptions
    _get(_module_name()).error(None)

def id(logger_func, __id__=None, msg=None, *args, **kwargs):
    """
    Prepends an id to the message
    """
    if __id__ and msg:
        key = '_'.join([Formatter.ID_KEY, 'color'])
        kwargs[key] = __id__
        msg = ''.join(['({', key, '}) ', msg])

    logger_func(msg, *args, **kwargs)

# ######################################################################

DEBUG    = logging.DEBUG
INFO     = logging.INFO
WARNING  = logging.WARNING
ERROR    = logging.ERROR
CRITICAL = logging.CRITICAL

def set_level(level, root=True):
    """
    Sets the level for either the root logger or the calling module's logger
    """
    name = None if root else _module_name()
    _get(name).setLevel(level)

def get_level():
    """
    Gets the effective level for the calling module's logger
    """
    _get(_module_name()).getEffectiveLevel()

def is_enabled_for(level):
    """
    Returns the current module's effective logger threshold. See:
    https://docs.python.org/2/library/logging.html#logging.Logger.isEnabledFor
    """
    return _get(_module_name()).isEnabledFor(level)

def add_filter(filt, root=True):
    """
    Adds filter {filt} to either the root logger or the current module's logger
    """
    name = None if root else _module_name()
    _get(name).addFilter(filt)

def remove_filter(filt, root=True):
    """
    Removes filter {filt} to either the root logger or the current module's
    logger
    """
    name = None if root else _module_name()
    _get(name).removeFilter(filt)

def add_handler(handler, root=True):
    """
    Adds {handler} to either the root logger or current module's logger
    """
    name = None if root else _module_name()
    _get(name).addHandler(handler)

def remove_handler(handler, root=True):
    """
    Remove {handler} to either the root logger or current module's logger
    """
    name = None if root else _module_name()
    _get(name).removeHandler(handler)

def clear_handlers(root=True):
    """
    Removes all handlers for either the root logger or current module's logger
    """
    name = None if root else _module_name()
    logger = _get(name)
    while logger.handlers:
        logger.removeHandler(logger.handlers[-1])


__all__ = [
        'debug',
        'info',
        'warn',
        'error',
        'critical',
        'exception',
        'id',

        'DEBUG',
        'INFO',
        'WARNING',
        'ERROR',
        'CRITICAL',
        'set_level',
        'get_level',
        'is_enabled_for',
        'add_filter',
        'remove_filter',
        'add_handler',
        'remove_handler',
]

