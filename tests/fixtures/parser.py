import pickle
import os
import sys

import pytest

if sys.version_info.major < 3:
    import mock
else:
    import unittest.mock as mock


def _load_pickle(*prefix, suffix='pickle'):
    """
    Returns the path to the pickle data

    Assumes that the path is: '{prefix}.py{major}.{suffix}'
    """
    path = os.path.join('tests', 'fixtures', 'pickles', *prefix)
    path = '{0}.py{1}.{2}'.format(path, sys.version_info.major, suffix)
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='session')
def linstahh():
    """ praw.models.Comment containing a soft-linked instagram user """
    return _load_pickle('linstahh')

@pytest.fixture(scope='session')
def natalieannworth():
    """ praw.models.Comment containing a soft-linked instagram user """
    return _load_pickle('natalieannworth')

@pytest.fixture(scope='session')
def tiffanie_marie():
    """ praw.models.Comment containing a soft-linked instagram user """
    return _load_pickle('tiffanie.marie')

@pytest.fixture(scope='session')
def haileypandolfi():
    """ praw.models.Comment containing a hard-linked instagram user """
    return _load_pickle('haileypandolfi')

@pytest.fixture(scope='session')
def viktoria_kay():
    """ praw.models.Comment containing a hard-linked instagram user """
    return _load_pickle('viktoria_kay')

@pytest.fixture(scope='session')
def ig_media_link():
    """ praw.models.Comment containing a instagram media link """
    return _load_pickle('medialink')

@pytest.fixture(scope='session')
def ig_media_link_no_trailing_slash():
    """
    praw.models.Comment containing a instagram media link with no trailing slash
    """
    return _load_pickle('medialink_notrailingslash')

@pytest.fixture(scope='session')
def parenthesis_user():
    """
    praw.models.Comment posted by AutoModerator containing a soft-linked user
    """
    return _load_pickle('parenthesis_user')

@pytest.fixture(scope='session')
def yassibenitez():
    """
    praw.models.Comment containing a soft-linked user (IG: ...)
    """
    return _load_pickle('yassibenitez')

@pytest.fixture(scope='session')
def vyvan_le():
    """
    praw.models.Comment containing a soft-linked user without '@'
    """
    return _load_pickle('vyvan.le')

@pytest.fixture(scope='session')
def hanny_madani():
    """
    praw.models.Comment containing a soft-linked user without '@' (... on instagram)
    """
    return _load_pickle('hanny_madani')

@pytest.fixture(scope='session')
def kaja_sbn():
    """
    praw.models.Comment containing a soft-linked user without '@' (... on instagram)
    """
    return _load_pickle('kaja_sbn')

@pytest.fixture(scope='session')
def eva_lo_dimelo():
    """
    praw.models.Comment containing a soft-linked user without '@' (... on IG)
    """
    return _load_pickle('eva_lo_dimelo')

@pytest.fixture(scope='session')
def chaileeson():
    """
    praw.models.Comment containing a soft-linked user without '@' (... on instagram)
    """
    return _load_pickle('chaileeson')

@pytest.fixture(scope='session')
def deliahatesyou():
    """
    praw.models.Comment containing a soft-linked user without '@' (... (IG))
    """
    return _load_pickle('deliahatesyou')

@pytest.fixture(scope='session')
def jessicabolusi_medialink():
    """
    praw.models.Comment containing an instagram media link with a user profile
    defined in its query
    """
    return _load_pickle('jessicabolusi_medialink')

@pytest.fixture(scope='session')
def thanks_():
    """
    praw.models.Comment containing the word 'Thanks'
    """
    return _load_pickle('thanks')

@pytest.fixture(scope='session')
def youre_():
    """
    praw.models.Comment containing the word 'You\'re'
    """
    return _load_pickle('youre')

@pytest.fixture(scope='session')
def perfection_():
    """
    praw.models.Comment containing the word 'Perfection.'
    """
    return _load_pickle('perfection')

@pytest.fixture(scope='session')
def whosethat():
    """
    praw.models.Comment containing the string 'Who is that?'
    """
    return _load_pickle('whosethat')

@pytest.fixture(scope='session')
def on_insta_rant():
    """
    praw.models.Comment rant containing the string 'on Insta'
    """
    return _load_pickle('on_insta_rant')

