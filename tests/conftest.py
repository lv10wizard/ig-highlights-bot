import pytest

def load_pickle(*prefix, suffix='pickle'):
    """
    Returns the path to the pickle data

    Assumes that the path is: '{prefix}.py{major}.{suffix}'
    """
    import sys

    path = os.path.join('tests', 'fixtures', 'pickles', *prefix)
    path = '{0}.py{1}.{2}'.format(path, sys.version_info.major, suffix)
    with open(path, 'rb') as fd:
        return pickle.load(fd)

@pytest.fixture(scope='module')
def comment():
    """
    Returns a mock praw.models.Comment
    """
    submission = reddit.submission()
    subreddit = reddit.subreddit()
    comment = reddit.comment()
    comment.submission = submission
    comment.subreddit = subreddit
    return comment

from .fixtures import reddit
# https://gist.github.com/peterhurford/09f7dcda0ab04b95c026c60fa49c2a68
from .fixtures.config import *
from .fixtures.database import *
from .fixtures.logger import *
from .fixtures.formatter import *
from .fixtures.parser import *


@pytest.fixture(scope='module')
def submission():
    """
    Returns a mock praw.models.Submission
    """
    submission = reddit.submission()
    subreddit = reddit.subreddit()
    submission.subreddit = subreddit
    return submission

@pytest.fixture(scope='module')
def subreddit():
    """
    Returns a mock praw.models.Subreddit
    """
    return reddit.subreddit()

@pytest.fixture(scope='session')
def _cassiebrown_bot_reply():
    """
    a bot praw.models.Comment reply containing the instagram user
    '_cassiebrown_'
    """
    # TODO: py2 version (cid = 'dog4q9y')
    return load_pickle('_cassiebrown_bot_reply')

