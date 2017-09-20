from contextlib import contextmanager
import logging

from src.util.logger.classes import (
        _Logger,
        _lock,
)
from src.util.modules import expose_modules


logging.setLoggerClass(_Logger)

@contextmanager
def lock():
    """
    Exposes the internal lock mechanism for use in 'with' statements
    """
    with _lock:
        yield

__all__ = expose_modules(__file__, __name__, locals())

