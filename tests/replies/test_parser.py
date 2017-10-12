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
    p = Parser(parenthesis_user)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_matches_non_english_word(vyvan_le):
    p = Parser(vyvan_le)
    assert not p.ig_links
    assert p.ig_usernames == ['vyvan.le']

def test_parser_matches_instagram_prefix(yassibenitez):
    p = Parser(yassibenitez)
    assert not p.ig_links
    assert p.ig_usernames == ['yassibenitez']

def test_parser_matches_on_instagram_suffix(hanny_madani, kaja_sbn):
    H = Parser(hanny_madani)
    assert not H.ig_links
    assert H.ig_usernames == ['Hanny_madani']

    K = Parser(kaja_sbn)
    assert not K.ig_links
    assert K.ig_usernames == ['kaja_sbn']

def test_parser_matches_user_linked_in_query(jessicabolusi_medialink):
    J = Parser(jessicabolusi_medialink)
    assert J.ig_links
    assert J.ig_usernames == ['jessicabolusi']

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
    'tiffanie_marie', 'tiffanie.marie', 'jessicabolusi',
])
def test_parser_does_not_overmatch_jargon(word):
    assert not Parser.is_jargon(word)

def test_parser_does_not_match_thanks(thanks_):
    # 'Thanks'
    p = Parser(thanks_)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_youre(youre_):
    # 'You\'re'
    p = Parser(youre_)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_perfection(perfection_):
    # 'Perfection. '
    p = Parser(perfection_)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_whosethat(whosethat):
    # 'Who is that? '
    p = Parser(whosethat)
    assert not p.ig_links
    assert not p.ig_usernames

