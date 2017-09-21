import logging
import sys

import pytest

from src.util.logger import (
        classes as logger_classes,
        formatter as logger_formatter,
        methods as logger_methods,
)


__LOGGER = None

def module_logger():
    global __LOGGER

    if not __LOGGER:
        name = logger_methods._module_name()
        logger = logger_methods._get(name)
        handler = logger_classes.ProcessStreamHandler(stream=sys.stdout)
        handler.setFormatter(logger_formatter.Formatter(fmt=logger_formatter.Formatter.FORMAT_NO_DATE))
        logger.addHandler(handler)
        __LOGGER = logger
    return __LOGGER


def test_module_name():
    assert logger_methods._module_name() == __name__

def test_root_logger_initialized(root_logger):
    assert root_logger.name == logger_methods.ROOT

def test_module_logger_initialized():
    assert module_logger().name == logger_methods.ROOT + '.' + __name__

def test_only_one_root_logger(root_logger):
    root = logger_methods._get()
    assert root_logger is root

def test_only_one_module_logger():
    name = logger_methods._module_name()
    logger = logger_methods._get(name)
    assert logger is module_logger()

def test_root_logger_is_custom_logger_instance(root_logger):
    assert isinstance(root_logger, logger_classes._Logger)

def test_module_logger_is_custom_logger_instance():
    assert isinstance(module_logger(), logger_classes._Logger)

def test_logger_adds_kwargs(root_logger):
    record = root_logger.makeRecord(
            root_logger.name, # name
            logging.DEBUG, # level
            'test', # fn
            69, # lno
            'TEST', # msg
            (), # args
            None, # exc_info
            foo='bar',
            baz='blah',
    )
    assert hasattr(record, 'kwargs')
    assert isinstance(record.kwargs, dict)
    assert record.kwargs['foo'] == 'bar'
    assert record.kwargs['baz'] == 'blah'

LEVEL_TESTS = [
    logging.DEBUG,
    logging.INFO,
    logging.WARNING,
    logging.ERROR,
    logging.CRITICAL,
]

@pytest.mark.parametrize('level', LEVEL_TESTS)
def test_set_level_root(root_logger, level):
    logger_methods.set_level(level)
    assert root_logger.getEffectiveLevel() == level

@pytest.mark.parametrize('level', LEVEL_TESTS)
def test_set_level_module(level):
    logger_methods.set_level(level, root=False)
    assert module_logger().getEffectiveLevel() == level

def test_get_level_root(root_logger):
    logger_methods.set_level(logging.WARNING)
    assert logger_methods.get_level() == logging.WARNING
    logger_methods.set_level(logging.DEBUG)
    assert logger_methods.get_level() == logging.DEBUG

def test_get_level_module():
    logger_methods.set_level(logging.WARNING, root=False)
    assert logger_methods.get_level(root=False) == logging.WARNING
    logger_methods.set_level(logging.DEBUG, root=False)
    assert logger_methods.get_level(root=False) == logging.DEBUG

def test_is_enabled_for():
    logger_methods.set_level(logging.ERROR, root=False)
    assert logger_methods.is_enabled_for(logging.DEBUG) is False
    assert logger_methods.is_enabled_for(logging.INFO) is False
    assert logger_methods.is_enabled_for(logging.WARNING) is False
    assert logger_methods.is_enabled_for(logging.ERROR) is True
    assert logger_methods.is_enabled_for(logging.CRITICAL) is True

__FILTER = logging.Filter()

def test_add_filter_root(root_logger):
    logger_methods.add_filter(__FILTER)
    assert __FILTER in root_logger.filters

def test_remove_filter_root(root_logger):
    logger_methods.add_filter(__FILTER)
    logger_methods.remove_filter(__FILTER)
    assert __FILTER not in root_logger.filters

def test_add_filter_module():
    logger_methods.add_filter(__FILTER, root=False)
    assert __FILTER in module_logger().filters

def test_remove_filter_module():
    logger_methods.add_filter(__FILTER, root=False)
    logger_methods.remove_filter(__FILTER, root=False)
    assert __FILTER not in module_logger().filters

__HANDLER = logging.StreamHandler()

def test_add_handler_root(root_logger):
    logger_methods.add_handler(__HANDLER)
    assert __HANDLER in root_logger.handlers

def test_remove_handler_root(root_logger):
    logger_methods.add_handler(__HANDLER)
    logger_methods.remove_handler(__HANDLER)
    assert __HANDLER not in root_logger.handlers

def test_add_handler_module():
    logger_methods.add_handler(__HANDLER, root=False)
    assert __HANDLER in module_logger().handlers

def test_remove_handler_module(root_logger):
    logger_methods.add_handler(__HANDLER, root=False)
    logger_methods.remove_handler(__HANDLER, root=False)
    assert __HANDLER not in module_logger().handlers

def test_clear_handlers_root(root_logger):
    logger_methods.add_handler(__HANDLER)
    logger_methods.clear_handlers()
    assert len(root_logger.handlers) == 0

def test_clear_handlers_module(root_logger):
    logger_methods.add_handler(__HANDLER, root=False)
    logger_methods.clear_handlers(root=False)
    assert len(module_logger().handlers) == 0

# ######################################################################

# TODO: test Formatter methods, handles unicode
#def test_

