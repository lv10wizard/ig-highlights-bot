import pickle
import os
import sys

import pytest

if sys.version_info.major < 3:
    import mock
else:
    import unittest.mock as mock


def _pickle_path(*prefix, suffix='pickle'):
    """
    Returns the path to the pickle data

    Assumes that the path is: '{prefix}.py{major}.{suffix}'
    """
    path = os.path.join('tests', 'fixtures', 'pickles', *prefix)
    return '{0}.py{1}.{2}'.format(path, sys.version_info.major, suffix)

@pytest.fixture(scope='session')
def linstahh():
    """ praw.models.Comment containing a soft-linked instagram user """
    path = _pickle_path('linstahh')
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def natalieannworth():
    """ praw.models.Comment containing a soft-linked instagram user """
    path = _pickle_path('natalieannworth')
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def tiffanie_marie():
    """ praw.models.Comment containing a soft-linked instagram user """
    path = _pickle_path('tiffanie.marie')
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def haileypandolfi():
    """ praw.models.Comment containing a hard-linked instagram user """
    path = _pickle_path('haileypandolfi')
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def viktoria_kay():
    """ praw.models.Comment containing a hard-linked instagram user """
    path = _pickle_path('viktoria_kay')
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def ig_media_link():
    """ praw.models.Comment containing a instagram media link """
    path = _pickle_path('medialink')
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def parenthesis_user():
    """
    praw.models.Comment posted by AutoModerator containing a soft-linked user
    """
    path = _pickle_path('parenthesis_user')
    with open(path, 'rb') as fd:
        return pickle.load(fd)

