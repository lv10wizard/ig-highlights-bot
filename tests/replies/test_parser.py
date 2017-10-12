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
    assert not Instagram.IG_USER_STRING_REGEX.search(parenthesis_user.body.strip())

    p = Parser(parenthesis_user)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_matches_non_english_word(vyvan_le):
    assert not Instagram.IG_LINK_REGEX.search(vyvan_le.body_html)
    assert not Instagram.IG_USER_REGEX.search(vyvan_le.body)
    assert Instagram.IG_USER_STRING_REGEX.search(vyvan_le.body.strip())

    p = Parser(vyvan_le)
    assert not p.ig_links
    assert p.ig_usernames == ['vyvan.le']

def test_parser_does_not_match_thanks(thanks_):
    # 'Thanks'
    assert not Instagram.IG_LINK_REGEX.search(thanks_.body_html)
    assert not Instagram.IG_USER_REGEX.search(thanks_.body)
    assert Instagram.IG_USER_STRING_REGEX.search(thanks_.body.strip())

    p = Parser(thanks_)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_youre(youre_):
    # 'You\'re'
    assert not Instagram.IG_LINK_REGEX.search(youre_.body_html)
    assert not Instagram.IG_USER_REGEX.search(youre_.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(youre_.body.strip())

    p = Parser(youre_)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_perfection(perfection_):
    # 'Perfection. '
    assert not Instagram.IG_LINK_REGEX.search(perfection_.body_html)
    assert not Instagram.IG_USER_REGEX.search(perfection_.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(perfection_.body.strip())

    p = Parser(perfection_)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_whosethat(whosethat):
    # 'Who is that? '
    assert not Instagram.IG_LINK_REGEX.search(whosethat.body_html)
    assert not Instagram.IG_USER_REGEX.search(whosethat.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(whosethat.body.strip())

    p = Parser(whosethat)
    assert not p.ig_links
    assert not p.ig_usernames

