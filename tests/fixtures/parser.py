import pickle
import os
import sys

import pytest

if sys.version_info.major < 3:
    import mock
else:
    import unittest.mock as mock


def _pickle_path(prefix, suffix='pickle'):
    """
    Returns the path to the pickle data

    Assumes that the path is: '{prefix}.py{major}.{suffix}'
    """
    return '{0}.py{1}.{2}'.format(prefix, sys.version_info.major, suffix)


@pytest.fixture(scope='session')
def linstahh():
    path = _pickle_path(os.path.join('tests/fixtures/pickles/linstahh'))
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def natalieannworth():
    path = _pickle_path(os.path.join('tests/fixtures/pickles/natalieannworth'))
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def tiffanie_marie():
    path = _pickle_path(os.path.join('tests/fixtures/pickles/tiffanie.marie'))
    with open(path, 'rb') as fd:
        return pickle.load(fd)

