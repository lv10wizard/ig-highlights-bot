import os
import re

import pytest
from six.moves import getcwd

import constants
from src import config


@pytest.mark.parametrize('path,expected', [
    ('~', os.path.realpath(os.environ['HOME'])),
    ('foobar', os.path.join(getcwd(), 'foobar')),
    ('', ''),
    (None, ''),
])
def test_config_resolve_path(path, expected):
    assert config.resolve_path(path) == expected

@pytest.mark.parametrize('time_str,expected', [
    ('123', 123),
    ('69s', 69),
    ('43m', 43 * 60),
    ('420h', 420 * 60 * 60),
    ('1d', 24 * 60 * 60),
    ('3w', 3 * 7 * 24 * 60 * 60),
    ('2M', 2 * 30 * 24 * 60 * 60),
    ('322Y', 322 * 365 * 24 * 60 * 60),
    ('10m 10s', 10 * 60 + 10),
    ('32.2h 69.420m', 32.2 * 60 * 60 + 69.420 * 60),
    ('69m! 420s?', 69 * 60 + 420),
    ('you are doing that too much. try again in 9 minutes.', 9 * 60),
])
def test_config_parse_time(time_str, expected):
    assert config.parse_time(time_str) == expected

def test_config_parse_time_complex():
    time_str = '1w 2 d 3h 4  m 106 10Y 5M'
    expected = (
            1 * 7 * 24 * 60 * 60 # 1w
            + 2 * 24 * 60 * 60 # 2d
            + 3 * 60 * 60 # 3h
            + 4 * 60 # 4m
            + 106 # 106
            + 10 * 365 * 24 * 60 * 60 # 10Y
            + 5 * 30 * 24 * 60 * 60 # 5M
    )
    assert config.parse_time(time_str) == expected

def test_config_parse_time_no_ending_unit():
    assert config.parse_time('6h 9m 4') == (6 * 60 * 60 + 9 * 60 + 4)

def test_config_parse_time_duplicate_unit():
    assert config.parse_time('69h 420h') == 69 * 60 * 60

@pytest.mark.parametrize('time_str', [
    'foobar baz',
    '10a2.0e5z',
    '69z',
])
def test_config_parse_time_invalid_time(time_str):
    with pytest.raises(config.InvalidTime):
        config.parse_time(time_str)

def _path(tmpdir_factory):
    path = ('foo', 'bar', config.Config.FILENAME)
    return tmpdir_factory.getbasetemp().join(*path)

def test_config_constructor_creates_directories(tmpdir_factory):
    path = _path(tmpdir_factory)
    assert not path.check()
    c = config.Config(str(path))
    assert path.check()

def test_config__str__(tmpdir_factory):
    path = _path(tmpdir_factory)
    assert str(config.Config(str(path))) == config.Config.FILENAME

@pytest.mark.parametrize('attr,expected', [
    ('praw_sitename', constants.DEFAULT_APP_NAME),

    ('app_name', constants.DEFAULT_APP_NAME),
    ('send_debug_pm', False),
    ('num_highlights_per_ig_user', 15),
    ('max_replies_per_comment', 2),
    ('max_replies_per_post', 15),
    ('max_replies_in_comment_thread', 3),
    ('delete_comment_threshold', -5),
    ('add_subreddit_threshold', 5),
    ('blacklist_temp_ban_time', config.parse_time('3d')),
    ('bad_actor_expire_time', config.parse_time('1d')),
    ('bad_actor_threshold', 3),

    ('instagram_cache_expire_time', config.parse_time('7d')),
    ('min_follower_count', 1000),

    ('logging_path',
        config.resolve_path(
            os.path.join(constants.DATA_ROOT_DIR, 'logs'))),
    ('logging_level', 'INFO'),
    ('colorful_logs', True),
])
def test_config_properties(cfg, attr, expected):
    assert getattr(cfg, attr) == expected

def test_config_fallback_properties(empty_cfg):
    fallback = empty_cfg._Config__fallback
    properties = [
            attr for attr in dir(empty_cfg)
            if (
                not attr.startswith('_')
                and attr.count('_') > 0
                and re.search(r'^[a-z]', attr)
            )
    ]
    for prop in properties:
        # TODO: test against the actual fallback values
        # ..maybe read ./bot.cfg and test against that?
        assert getattr(empty_cfg, prop) is not None

