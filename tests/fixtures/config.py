import pytest

from src import config


TEST_CONFIG = '''
[PRAW]
praw_sitename = igHighlightsBot

[REDDIT]
app_name = igHighlightsBot
send_debug_pm = false
num_highlights_per_ig_user = 15
max_replies_per_comment = 2
max_replies_per_post = 15
max_replies_in_comment_thread = 3
add_subreddit_threshold = 5
blacklist_temp_ban_time = 3d
bad_actor_expire_time = 1d
bad_actor_threshold = 3

[INSTAGRAM]
instagram_cache_expire_time = 7d

[LOGGING]
logging_path = %(data_dir)s/logs
logging_level = INFO

'''

@pytest.fixture(scope='session')
def cfg(tmpdir_factory):
    """
    Returns a test config which lasts for the entire test session
    """
    path = tmpdir_factory.getbasetemp().join('config', 'test.cfg')
    path.write(TEST_CONFIG, ensure=True)
    return config.Config(str(path))


__all__ = [
        'cfg',
]

