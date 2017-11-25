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
delete_comment_threshold = -5
add_subreddit_threshold = 5
blacklist_temp_ban_time = 3d
bad_actor_expire_time = 1d
bad_actor_threshold = 3

[INSTAGRAM]
instagram_cache_expire_time = 7d
min_follower_count = 1000

[IMGUR]
imgur_upload_enabled = true
imgur_client_id = foobar
imgur_client_secret = qwerty
imgur_highlights_credits_buffer = 1000

[LOGGING]
logging_path = %(data_dir)s/logs
logging_level = INFO
colorful_logs = true

'''

@pytest.fixture(scope='session')
def cfg(tmpdir_factory):
    """
    Returns a test config which lasts for the entire test session
    """
    path = tmpdir_factory.getbasetemp().join('config', 'test.cfg')
    path.write(TEST_CONFIG, ensure=True)
    return config.Config(str(path))

@pytest.fixture(scope='session')
def empty_cfg(tmpdir_factory):
    """ An empty test config file """
    path = tmpdir_factory.getbasetemp().join('config', 'test_empty.cfg')
    path.write('', ensure=True)
    return config.Config(str(path))

