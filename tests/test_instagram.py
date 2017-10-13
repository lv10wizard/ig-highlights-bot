from src.instagram import Instagram


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

def test_instagram_ignores_automod(parenthesis_user):
    assert not Instagram.IG_LINK_REGEX.search(parenthesis_user.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(parenthesis_user.body)
    assert Instagram.IG_USER_REGEX.search(parenthesis_user.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(parenthesis_user.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(parenthesis_user.body.strip())

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

def test_instagram_matches_instagram_prefix(yassibenitez):
    assert not Instagram.IG_LINK_REGEX.search(yassibenitez.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(yassibenitez.body)
    user_match = Instagram.IG_USER_REGEX.search(yassibenitez.body)
    assert user_match
    assert user_match.group(1) == 'yassibenitez'
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(yassibenitez.body.strip())
    assert user_str_match
    assert user_str_match.group(1) == 'yassibenitez'

def test_isntagram_does_not_over_match_instagram_prefix(
        hanny_madani, kaja_sbn, eva_lo_dimelo, chaileeson, deliahatesyou,
):
    assert not Instagram.IG_LINK_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_USER_REGEX.search(hanny_madani.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(hanny_madani.body.strip())
    assert user_str_match
    assert not user_str_match.group(1)

    assert not Instagram.IG_LINK_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_USER_REGEX.search(kaja_sbn.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(kaja_sbn.body.strip())
    assert user_str_match
    assert not user_str_match.group(1)

    assert not Instagram.IG_LINK_REGEX.search(eva_lo_dimelo.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(eva_lo_dimelo.body)
    assert not Instagram.IG_USER_REGEX.search(eva_lo_dimelo.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(eva_lo_dimelo.body.strip())
    assert user_str_match
    assert not user_str_match.group(1)

    assert not Instagram.IG_LINK_REGEX.search(chaileeson.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(chaileeson.body)
    assert not Instagram.IG_USER_REGEX.search(chaileeson.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(chaileeson.body.strip())
    assert user_str_match
    assert not user_str_match.group(1)

    assert not Instagram.IG_LINK_REGEX.search(deliahatesyou.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(deliahatesyou.body)
    assert not Instagram.IG_USER_REGEX.search(deliahatesyou.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(deliahatesyou.body.strip())
    assert user_str_match
    assert not user_str_match.group(1)

def test_instagram_matches_on_instagram_suffix(
        hanny_madani, kaja_sbn, eva_lo_dimelo, chaileeson, deliahatesyou,
):
    assert not Instagram.IG_LINK_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_USER_REGEX.search(hanny_madani.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(hanny_madani.body.strip())
    assert user_str_match
    assert 'Hanny_madani' in user_str_match.groups()

    assert not Instagram.IG_LINK_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_USER_REGEX.search(kaja_sbn.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(kaja_sbn.body.strip())
    assert user_str_match
    assert 'kaja_sbn' in user_str_match.groups()

    assert not Instagram.IG_LINK_REGEX.search(eva_lo_dimelo.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(eva_lo_dimelo.body)
    assert not Instagram.IG_USER_REGEX.search(eva_lo_dimelo.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(eva_lo_dimelo.body.strip())
    assert user_str_match
    assert 'eva_lo_dimelo' in user_str_match.groups()

    assert not Instagram.IG_LINK_REGEX.search(chaileeson.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(chaileeson.body)
    assert not Instagram.IG_USER_REGEX.search(chaileeson.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(chaileeson.body.strip())
    assert user_str_match
    assert 'chaileeson' in user_str_match.groups()

    assert not Instagram.IG_LINK_REGEX.search(deliahatesyou.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(deliahatesyou.body)
    assert not Instagram.IG_USER_REGEX.search(deliahatesyou.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(deliahatesyou.body.strip())
    assert user_str_match
    assert 'Deliahatesyou' in user_str_match.groups()

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

def test_instagram_does_not_match_on_insta(on_insta_rant):
    # '[...] on Insta [...]'
    assert not Instagram.IG_LINK_REGEX.search(on_insta_rant.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(on_insta_rant.body)
    assert not Instagram.IG_USER_REGEX.search(on_insta_rant.body)
    assert Instagram.IG_USER_STRING_REGEX.search(on_insta_rant.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(on_insta_rant.body.strip())

