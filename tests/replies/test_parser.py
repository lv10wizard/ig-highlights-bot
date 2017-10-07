import praw
import pytest

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

