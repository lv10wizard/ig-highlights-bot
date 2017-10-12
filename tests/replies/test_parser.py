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

def test_parser_matches_instagram_prefix(yassibenitez):
    assert not Instagram.IG_LINK_REGEX.search(yassibenitez.body_html)
    user_match = Instagram.IG_USER_REGEX.search(yassibenitez.body)
    assert user_match
    assert user_match.group(1) == 'yassibenitez'
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(yassibenitez.body.strip())
    assert user_str_match
    assert user_str_match.group(1) == 'yassibenitez'

    p = Parser(yassibenitez)
    assert not p.ig_links
    assert p.ig_usernames == ['yassibenitez']

def test_parser_matches_on_instagram_suffix(hanny_madani, kaja_sbn):
    assert not Instagram.IG_LINK_REGEX.search(hanny_madani.body_html)
    assert not Instagram.IG_USER_REGEX.search(hanny_madani.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(hanny_madani.body.strip())
    assert user_str_match
    assert user_str_match.group(1) == 'Hanny_madani'
    assert not Instagram.IG_LINK_REGEX.search(kaja_sbn.body_html)
    assert not Instagram.IG_USER_REGEX.search(kaja_sbn.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(kaja_sbn.body.strip())
    assert user_str_match
    assert user_str_match.group(1) == 'kaja_sbn'

    H = Parser(hanny_madani)
    assert not H.ig_links
    assert H.ig_usernames == ['Hanny_madani']

    K = Parser(kaja_sbn)
    assert not K.ig_links
    assert K.ig_usernames == ['kaja_sbn']

@pytest.mark.parametrize('word', [
    'ha', 'haha!', 'haahaha', 'bahaahaha', 'lol', 'LOL', 'lol!!', 'loooool',
    'lololol', 'lloolollol', 'lmao', 'LMAO', 'lmfao', 'LMFAO', 'rofl', 'lulz',
    'roflmao', 'rofllmao', 'wtfffff', 'omg', 'OMFGGG', 'woooops', 'WOoOOSH',
    'FTFY', 'wowsers', 'WTF!?', 'dafuq', 'bruhhh', 'kek', 'yaaaassss', 'duuude',
    'bae', '2spooky4me', '3spoopy5me', '8cute10me', 'me_irl', '2meirl', 'ick',
    'niceeeeeeeeeeeeeeeeeeee', 'noice', 'gracias', 'o_O', 'O.o', 'Whelp',
    'soooo..', 'Wowza!', 'butterface', 'hellooooooo', 'Mmmmm...', 'gotdayumn!',
    'GODDAYUMMNNN', 'dayuuuuum', 'TIL', 'bae', 'awww', 'asl?', 'yw', 'shopped',
    'Photoshopped', 'Enhaaaaance', 'zooooommm', 'ooookey', 'Ooof.', 'schwifty',
    'lawwwwd', 'lawdyyy', 'goddamn', 'schlurp', 'gaaaggg', 'gaaaayyy',
    'nnnaaaaammee', 'makelinesstraightagain', 'wut', 'wat', 'Hhnnnnng', 'fml',
    'HnnNNNGGG', 'Whoosh', 'wHOooOoosh',
])
def test_parser_detects_jargon(word):
    assert Parser.is_jargon(word)

@pytest.mark.parametrize('word', [
    'Daring', 'gorgeous', 'beautiful', 'google', 'vyvan.le', 'Hanny_madani',
    'kaja_sbn', 'haileypandolfi', 'viktoria_kay', 'linstahh', 'natalieannworth',
    'tiffanie_marie', 'tiffanie.marie',
])
def test_parser_does_not_overmatch_jargon(word):
    assert not Parser.is_jargon(word)

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

def test_parser_does_not_match_on_insta(on_insta_rant):
    # '[...] on Insta [...]'
    assert not Instagram.IG_LINK_REGEX.search(on_insta_rant.body_html)
    assert not Instagram.IG_USER_REGEX.search(on_insta_rant.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(on_insta_rant.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(on_insta_rant.body.strip())

