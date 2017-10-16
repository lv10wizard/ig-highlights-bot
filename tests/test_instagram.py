# -*- coding: UTF-8 -*-

import re

import pytest

from src.instagram import Instagram


USERNAME_REGEX = re.compile(
        r'^{0}$'.format(Instagram.USERNAME_PTN), flags=re.IGNORECASE
)

@pytest.mark.parametrize('string', [
    'foobar', '1foo', 'a', 'foo__', 'foo.bar.a_xx99_', '__blahhh',
])
def test_instagram_username_matches(string):
    assert USERNAME_REGEX.search(string)

@pytest.mark.parametrize('string', [
    'Touché', '.foobar', 'foobar..', 'foo..bar', '^', '$', 'asdf!',
])
def test_instagram_username_does_not_match(string):
    assert not USERNAME_REGEX.search(string)

@pytest.mark.parametrize('link,expected', [
    ('https://www.instagram.com/k.01.bulgakova/', 'k.01.bulgakova'),
    ('https://www.instagram.com/jadegrobler/', 'jadegrobler'),
    ('https://instagr.am/morganlux', 'morganlux'),
])
def test_instagram_matches_ig_links_strings(link, expected):
    match = Instagram.IG_LINK_REGEX.search(link)
    assert match
    assert match.group(2) == expected

@pytest.mark.parametrize('link', [
    'https://www.google.com/',
    'www.example.com',
    'http://localhost:8080',
    'https://www.reddit.com/r/EarthPorn/comments/76f6zg/this_glacial_iceberg_in_greenland_was_awesome/',
    'https://www.instagram.com/p/BaCrBOqn-8R/?hl=en',
])
def test_instagram_matches_does_not_overmatch_links_strings(link):
    assert not Instagram.IG_LINK_REGEX.search(link)

@pytest.mark.parametrize('link,expected', [
    ('https://www.instagram.com/p/BaLqVhPhv-Z/?taken-by=jadegrobler',
        'jadegrobler'),
    ('https://www.instagram.com/p/BZ8BtkXALZA/?taken-by=jadegrobler',
        'jadegrobler'),
    ('https://www.instagram.com/p/BZO5gp4D5ah/?taken-by=k.01.bulgakova',
        'k.01.bulgakova'),
    ('https://www.instagram.com/p/BaCrBOqn-8R/?hl=en&taken-by=saracalixtocr',
        'saracalixtocr'),
    ('https://www.instagram.com/p/BaCrBOqn-8R/?taken-by=saracalixtocr&hl=en',
        'saracalixtocr'),
])
def test_instagram_matches_ig_links_query_strings(link, expected):
    match = Instagram.IG_LINK_QUERY_REGEX.search(link)
    assert match
    assert match.group(1) == 'https://www.instagram.com'
    assert match.group(2) == expected

@pytest.mark.parametrize('string,expected', [
    ('@k.01.bulgakova', 'k.01.bulgakova'),
    (' @k.01.bulgakova', 'k.01.bulgakova'),
    (' @k.01.bulgakova ', 'k.01.bulgakova'),
    ('@k.01.bulgakova ', 'k.01.bulgakova'),
    ('(@k.01.bulgakova) ', 'k.01.bulgakova'),
    (' [@k.01.bulgakova] ', 'k.01.bulgakova'),
])
def test_instagram_matches_ig_user_strings(string, expected):
    match = Instagram.IG_USER_REGEX.search(string)
    assert match
    assert match.group(1) == expected

@pytest.mark.parametrize('string', [
    'This is her instagram: @foobar',
    '(IG): blahface__',
    'that\'s idont.care on insta',
    'rockopera on IG.',
    'Diablo_sam on IG. She\'s awesome. ',
    'Source: ig triippyunicorn',
])
def test_instagram_matches_has_ig_keyword_strings(string):
    assert Instagram.HAS_IG_KEYWORD_REGEX.search(string)

@pytest.mark.parametrize('string', [
    'IG: foobar maybe?',
    'is this @_blah on insta?',
])
def test_instagram_does_not_overmatch_has_ig_keyword_strings(string):
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(string)

@pytest.mark.parametrize('string,expected', [
    ('IG: foobar', 'foobar'),
    ('foobar on insta', 'foobar'),
    ('I\'m pretty sure this is foobar on insta', 'foobar'),
    ('Diablo_sam on IG. She\'s awesome. ', 'Diablo_sam'),
    ('Source: ig triippyunicorn', 'triippyunicorn'),
    ('stephxohaven on insta and snap', 'stephxohaven'),
])
def test_instagram_matches_potential_ig_user_strings(string, expected):
    match = Instagram.IG_USER_STRING_REGEX.search(string)
    assert match
    assert expected in match.groups()

@pytest.mark.parametrize('string', [
    'Yo that\'s not cool',
    'Story of my life.',
    'Sauce? sauce sauce',
    'Name?',
    'I\'m okay with this',
    'maybe blah on instagram? actually on second thought nvm',
])
def test_instagram_does_not_overmatch_potential_ig_user_strings(string):
    assert not Instagram.IG_USER_STRING_REGEX.search(string)

def test_instagram_matches_links(haileypandolfi, viktoria_kay):
    assert Instagram.IG_LINK_REGEX.search(haileypandolfi.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(haileypandolfi.body)
    assert not Instagram.IG_USER_REGEX.search(haileypandolfi.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(haileypandolfi.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(haileypandolfi.body.strip())

    assert Instagram.IG_LINK_REGEX.search(viktoria_kay.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(viktoria_kay.body)
    assert not Instagram.IG_USER_REGEX.search(viktoria_kay.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(viktoria_kay.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(viktoria_kay.body.strip())

# XXX: this test doesn't really make sense
def test_instagram_ignores_automod(parenthesis_user, automoderator_user_link):
    assert not Instagram.IG_LINK_REGEX.search(parenthesis_user.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(parenthesis_user.body)
    assert Instagram.IG_USER_REGEX.search(parenthesis_user.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(parenthesis_user.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(parenthesis_user.body.strip())

    assert Instagram.IG_LINK_REGEX.search(automoderator_user_link.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(automoderator_user_link.body)
    assert not Instagram.IG_USER_REGEX.search(automoderator_user_link.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(
            automoderator_user_link.body.strip()
    )
    assert Instagram.HAS_IG_KEYWORD_REGEX.search(
            automoderator_user_link.body.strip()
    )

def test_instagram_matches_non_english_word(vyvan_le):
    assert not Instagram.IG_LINK_REGEX.search(vyvan_le.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(vyvan_le.body)
    assert not Instagram.IG_USER_REGEX.search(vyvan_le.body)
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(vyvan_le.body.strip())
    assert Instagram.IG_USER_STRING_REGEX.search(vyvan_le.body.strip())

def test_instagram_does_not_match_media_links(
        ig_media_link, ig_media_link_no_trailing_slash
):
    assert not Instagram.IG_LINK_REGEX.search(ig_media_link.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(ig_media_link.body)
    assert not Instagram.IG_USER_REGEX.search(ig_media_link.body)
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(ig_media_link.body.strip())
    assert not Instagram.IG_USER_STRING_REGEX.search(ig_media_link.body.strip())

    assert not Instagram.IG_LINK_REGEX.search(ig_media_link_no_trailing_slash.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(ig_media_link_no_trailing_slash.body)
    assert not Instagram.IG_USER_REGEX.search(ig_media_link_no_trailing_slash.body)
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(
            ig_media_link_no_trailing_slash.body.strip()
    )
    assert not Instagram.IG_USER_STRING_REGEX.search(
            ig_media_link_no_trailing_slash.body.strip()
    )

def test_instagram_matches_instagram_prefix(
        yassibenitez, coffeequeennn,
):
    assert not Instagram.IG_LINK_REGEX.search(yassibenitez.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(yassibenitez.body)
    user_match = Instagram.IG_USER_REGEX.search(yassibenitez.body)
    assert user_match
    assert 'yassibenitez' in user_match.groups()
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(yassibenitez.body.strip())
    assert user_str_match
    assert user_str_match.group('prefix') == 'yassibenitez'

    assert not Instagram.IG_LINK_REGEX.search(coffeequeennn.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(coffeequeennn.body)
    assert not Instagram.IG_USER_REGEX.search(coffeequeennn.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(coffeequeennn.body.strip())
    assert user_str_match
    assert user_str_match.group('prefix') == '_coffeequeennn'

def test_isntagram_does_not_over_match_instagram_prefix(
        hanny_madani, kaja_sbn, eva_lo_dimelo, chaileeson, deliahatesyou,
):
    assert not Instagram.IG_LINK_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_USER_REGEX.search(hanny_madani.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(hanny_madani.body.strip())
    assert user_str_match
    assert not user_str_match.group('prefix')

    assert not Instagram.IG_LINK_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_USER_REGEX.search(kaja_sbn.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(kaja_sbn.body.strip())
    assert user_str_match
    assert not user_str_match.group('prefix')

    assert not Instagram.IG_LINK_REGEX.search(eva_lo_dimelo.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(eva_lo_dimelo.body)
    assert not Instagram.IG_USER_REGEX.search(eva_lo_dimelo.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(eva_lo_dimelo.body.strip())
    assert user_str_match
    assert not user_str_match.group('prefix')

    assert not Instagram.IG_LINK_REGEX.search(chaileeson.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(chaileeson.body)
    assert not Instagram.IG_USER_REGEX.search(chaileeson.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(chaileeson.body.strip())
    assert user_str_match
    assert not user_str_match.group('prefix')

    assert not Instagram.IG_LINK_REGEX.search(deliahatesyou.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(deliahatesyou.body)
    assert not Instagram.IG_USER_REGEX.search(deliahatesyou.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(deliahatesyou.body.strip())
    assert user_str_match
    assert not user_str_match.group('prefix')

def test_instagram_matches_on_instagram_suffix(
        hanny_madani, kaja_sbn, eva_lo_dimelo, chaileeson, deliahatesyou,
        stephxohaven,
):
    assert not Instagram.IG_LINK_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_USER_REGEX.search(hanny_madani.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(hanny_madani.body.strip())
    assert user_str_match
    assert user_str_match.group('suffix') == 'Hanny_madani'

    assert not Instagram.IG_LINK_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_USER_REGEX.search(kaja_sbn.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(kaja_sbn.body.strip())
    assert user_str_match
    assert user_str_match.group('suffix') == 'kaja_sbn'

    assert not Instagram.IG_LINK_REGEX.search(eva_lo_dimelo.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(eva_lo_dimelo.body)
    assert not Instagram.IG_USER_REGEX.search(eva_lo_dimelo.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(eva_lo_dimelo.body.strip())
    assert user_str_match
    assert user_str_match.group('suffix') == 'eva_lo_dimelo'

    assert not Instagram.IG_LINK_REGEX.search(chaileeson.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(chaileeson.body)
    assert not Instagram.IG_USER_REGEX.search(chaileeson.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(chaileeson.body.strip())
    assert user_str_match
    assert user_str_match.group('suffix') == 'chaileeson'

    assert not Instagram.IG_LINK_REGEX.search(deliahatesyou.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(deliahatesyou.body)
    assert not Instagram.IG_USER_REGEX.search(deliahatesyou.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(deliahatesyou.body.strip())
    assert user_str_match
    assert user_str_match.group('suffix') == 'Deliahatesyou'

    assert not Instagram.IG_LINK_REGEX.search(stephxohaven.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(stephxohaven.body)
    assert not Instagram.IG_USER_REGEX.search(stephxohaven.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(stephxohaven.body.strip())
    assert user_str_match
    assert user_str_match.group('suffix') == 'stephxohaven'

def test_instagram_matches_user_linked_in_query(jessicabolusi_medialink):
    assert not Instagram.IG_LINK_REGEX.search(jessicabolusi_medialink.body)
    assert Instagram.IG_LINK_QUERY_REGEX.search(jessicabolusi_medialink.body)
    assert not Instagram.IG_USER_REGEX.search(jessicabolusi_medialink.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(
            jessicabolusi_medialink.body.strip()
    )

def test_instagram_does_match_thanks(thanks_):
    # 'Thanks'
    assert not Instagram.IG_LINK_REGEX.search(thanks_.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(thanks_.body)
    assert not Instagram.IG_USER_REGEX.search(thanks_.body)
    assert Instagram.IG_USER_STRING_REGEX.search(thanks_.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(thanks_.body.strip())

def test_instagram_does_not_match_youre(youre_):
    # 'You\'re'
    assert not Instagram.IG_LINK_REGEX.search(youre_.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(youre_.body)
    assert not Instagram.IG_USER_REGEX.search(youre_.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(youre_.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(youre_.body.strip())

def test_instagram_does_not_match_perfection(perfection_):
    # 'Perfection. '
    assert not Instagram.IG_LINK_REGEX.search(perfection_.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(perfection_.body)
    assert not Instagram.IG_USER_REGEX.search(perfection_.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(perfection_.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(perfection_.body.strip())

def test_instagram_does_not_match_whosethat(whosethat):
    # 'Who is that?'
    assert not Instagram.IG_LINK_REGEX.search(whosethat.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(whosethat.body)
    assert not Instagram.IG_USER_REGEX.search(whosethat.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(whosethat.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(whosethat.body.strip())

@pytest.mark.xfail
def test_instagram_does_not_match_on_insta(on_insta_rant):
    # '[...] on Insta [...]'
    assert not Instagram.IG_LINK_REGEX.search(on_insta_rant.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(on_insta_rant.body)
    assert not Instagram.IG_USER_REGEX.search(on_insta_rant.body)
    # XXX: these fail (caught @ the parser level)
    assert not Instagram.IG_USER_STRING_REGEX.search(on_insta_rant.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(on_insta_rant.body.strip())

