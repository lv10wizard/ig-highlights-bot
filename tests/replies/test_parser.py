import praw
import pytest

from src.instagram import Instagram
from src.replies import Parser


def test_parser_init(linstahh):
    p = Parser(linstahh)
    assert bool(p.comment)
    assert isinstance(p.comment, praw.models.Comment)

def test_parser_ig_users_only(linstahh, natalieannworth, tiffanie_marie):
    L = Parser(linstahh)
    N = Parser(natalieannworth)
    T = Parser(tiffanie_marie)

    assert not L.ig_links
    assert not N.ig_links
    assert not T.ig_links
    assert L.ig_usernames == ['linstahh']
    assert N.ig_usernames == ['natalieannworth']
    assert T.ig_usernames == ['tiffanie.marie']

def test_parser_ig_links(haileypandolfi, viktoria_kay):
    H = Parser(haileypandolfi)
    V = Parser(viktoria_kay)

    assert bool(H.ig_links)
    assert H.ig_usernames == ['haileypandolfi']
    assert bool(V.ig_links)
    assert V.ig_usernames == ['viktoria_kay']

def test_parser_ig_media_link(ig_media_link):
    p = Parser(ig_media_link)

    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_ignores_automod(parenthesis_user):
    assert not Instagram.IG_LINK_REGEX.search(parenthesis_user.body_html)
    assert Instagram.IG_USER_REGEX.search(parenthesis_user.body)

    p = Parser(parenthesis_user)
    assert not p.ig_links
    assert not p.ig_usernames

