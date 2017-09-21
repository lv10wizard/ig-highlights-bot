import pytest

from .fixtures import reddit
from .fixtures.logger import *


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

