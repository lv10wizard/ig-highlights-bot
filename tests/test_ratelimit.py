import ctypes
import os
import multiprocessing
import time

import pytest

from src import ratelimit


_EVENT_TYPE = type(multiprocessing.Event())
_FLOAT_VALUE_TYPE = type(multiprocessing.Value(ctypes.c_float))

def _set_path(tmpdir_factory):
    # override the reset time save location
    ratelimit.Flag._PATH = str(tmpdir_factory.getbasetemp().join('ratelimit'))

def test_flag_clean_init(tmpdir_factory):
    _set_path(tmpdir_factory)

    if os.path.exists(ratelimit.Flag._PATH):
        os.remove(ratelimit.Flag._PATH)

    flag = ratelimit.Flag()
    assert not os.path.exists(ratelimit.Flag._PATH)
    assert bool(flag)
    assert isinstance(flag._event, _EVENT_TYPE)
    assert isinstance(flag._value, _FLOAT_VALUE_TYPE)
    assert flag._value.value == 0.0
    assert not os.path.exists(ratelimit.Flag._PATH)

def test_flag_load_init(tmpdir_factory):
    _set_path(tmpdir_factory)

    with open(ratelimit.Flag._PATH, 'w') as fd:
        fd.write(str(time.time() + 30))
    assert os.path.exists(ratelimit.Flag._PATH)

    flag = ratelimit.Flag()
    assert os.path.exists(ratelimit.Flag._PATH)
    assert flag._event.is_set()
    assert flag._value.value > 0

def test_flag_load_init_expired(tmpdir_factory):
    _set_path(tmpdir_factory)

    with open(ratelimit.Flag._PATH, 'w') as fd:
        fd.write(str(time.time() - 30))
    assert os.path.exists(ratelimit.Flag._PATH)

    flag = ratelimit.Flag()
    assert not os.path.exists(ratelimit.Flag._PATH)
    assert not flag._event.is_set()
    assert flag._value.value <= 0

def test_flag_value():
    flag = ratelimit.Flag()
    assert flag.value == 0

def test_flag_value_set_positive(tmpdir_factory):
    _set_path(tmpdir_factory)

    flag = ratelimit.Flag()
    flag.value = time.time() + 69
    assert os.path.exists(ratelimit.Flag._PATH)
    assert flag.value > 0
    assert flag._event.is_set()

def test_flag_value_set_non_positive(tmpdir_factory):
    _set_path(tmpdir_factory)

    flag = ratelimit.Flag()
    flag.value = 0
    assert not os.path.exists(ratelimit.Flag._PATH)
    assert flag.value <= 0
    assert not flag._event.is_set()

    flag.value = -1
    assert not os.path.exists(ratelimit.Flag._PATH)
    assert flag.value <= 0
    assert not flag._event.is_set()

def test_flag_remaining(tmpdir_factory):
    _set_path(tmpdir_factory)

    flag = ratelimit.Flag()
    flag.value = time.time() + 69
    assert flag.remaining > 0

def test_flag_is_set(tmpdir_factory):
    _set_path(tmpdir_factory)

    flag = ratelimit.Flag()
    flag.value = time.time() + 69
    assert flag.is_set()

# TODO? test_flag_wait => mock .wait?

