import pytest

from constants import(
        PREFIX_USER,
        PREFIX_SUBREDDIT,
)
from src import reddit


@pytest.mark.parametrize('name,expected', [
    ('/u/lv10wizard', (PREFIX_USER, 'lv10wizard')),
    ('u/lv10wizard', (PREFIX_USER, 'lv10wizard')),
    ('r/u_lv10wizard', (PREFIX_SUBREDDIT, 'u_lv10wizard')),
    ('/r/memes', (PREFIX_SUBREDDIT, 'memes')),
    ('r/memes', (PREFIX_SUBREDDIT, 'memes')),
    ('foobar', ('', 'foobar')),
    ('/a/blah', ('', '/a/blah')),
])
def test_split_prefixed_name(name, expected):
    assert reddit.split_prefixed_name(name) == expected

@pytest.mark.parametrize('name,err', [
    (123, TypeError),
    (None, TypeError),
    (object, TypeError),
])
def test_split_prefixed_name_raises(name, err):
    with pytest.raises(err):
        reddit.split_prefixed_name(name)

@pytest.mark.parametrize('name,expected', [
    ('/u/lv10wizard', False),
    ('u/lv10wizard', False),
    ('/r/u_lv10wizard', True),
    ('r/u_lv10wizard', True),
])
def test_is_subreddit(name, expected):
    assert reddit.is_subreddit(name) is expected

@pytest.mark.parametrize('name,expected', [
    ('/u/lv10wizard', True),
    ('u/lv10wizard', True),
    ('/r/u_lv10wizard', False),
    ('r/u_lv10wizard', False),
])
def test_is_user(name, expected):
    assert reddit.is_user(name) is expected

@pytest.mark.parametrize('prefix,expected', [
    (PREFIX_USER, True),
    (PREFIX_SUBREDDIT, False),
    (None, False),
    ('', False),
    (123, False),
])
def test_is_user_prefix(prefix, expected):
    assert reddit.is_user_prefix(prefix) is expected

@pytest.mark.parametrize('name,expected', [
    ('games', 'r/games'),
    ('u_lv10wizard', 'r/u_lv10wizard'),
])
def test_prefix_subreddit(name, expected):
    assert reddit.prefix_subreddit(name) == expected

@pytest.mark.parametrize('name,expected', [
    ('lv10wizard', 'u/lv10wizard'),
    ('_-O_O-_', 'u/_-O_O-_'),
])
def test_prefix_user(name, expected):
    assert reddit.prefix_user(name) == expected

def test_pack_subreddits():
    assert reddit.pack_subreddits(['games', 'memes', 'AskReddit']) == 'games+memes+AskReddit'

def test_unpack_subreddits():
    unpacked = reddit.unpack_subreddits('games+memes+AskReddit')
    assert len(unpacked) == 3

def test_display_id_comment(comment):
    assert reddit.display_id(comment) == 'u/lv10wizard/dmzb5qa'

def test_display_id_submission(submission):
    assert reddit.display_id(submission) == 'u/lv10wizard/6zztml'

def test_display_id_subreddit(subreddit):
    assert reddit.display_id(subreddit) == '3odt0'

def test_display_fullname_comment(comment):
    assert reddit.display_fullname(comment).startswith('t1_dmzb5qa')

def test_display_fullname_submission(submission):
    assert reddit.display_fullname(submission).startswith('t3_6zztml')

def test_display_fullname_subreddit(subreddit):
    assert reddit.display_fullname(subreddit).startswith('t5_3odt0')

# TODO? test reddit.Reddit object; I think would require refactor so that
# intermediate layer returns before calling underlying praw methods.

