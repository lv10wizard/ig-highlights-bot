import logging
import sys

if sys.version_info.major < 3:
    import mock
else:
    import unittest.mock as mock

import pytest

from src.util.logger import (
        formatter as logger_formatter,
        methods as logger_methods,
)


@pytest.fixture(scope='module')
def root_logger():
    """
    Returns the root logger
    """
    return logger_methods._get()

@pytest.fixture(scope='module')
def logger_formatter():
    """
    Returns a logger.Formatter
    """
    return logger_formatter.Formatter()

@pytest.fixture(scope='module')
def logrecord_debug():
    """
    Returns a LogRecord instance
    """
    return root_logger().makeRecord(
            root_logger().name,
            logging.DEBUG,
            'logrecord_debug',
            69,
            # TODO: msg, args, exc_info, func, extra, kwargs
            # ? is this needed?
    )


__all__ = [
        'root_logger',
]

