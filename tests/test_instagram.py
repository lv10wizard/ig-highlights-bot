from src.instagram import Instagram


def test_instagram_ignores_automod(parenthesis_user):
    assert not Instagram.IG_LINK_REGEX.search(parenthesis_user.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(parenthesis_user.body)
    assert Instagram.IG_USER_REGEX.search(parenthesis_user.body)
    assert not Instagram.IG_USER_STRING_REGEX.search(parenthesis_user.body.strip())

def test_instagram_matches_non_english_word(vyvan_le):
    assert not Instagram.IG_LINK_REGEX.search(vyvan_le.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(vyvan_le.body)
    assert not Instagram.IG_USER_REGEX.search(vyvan_le.body)
    assert Instagram.IG_USER_STRING_REGEX.search(vyvan_le.body.strip())

def test_instagram_matches_instagram_prefix(yassibenitez):
    assert not Instagram.IG_LINK_REGEX.search(yassibenitez.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(yassibenitez.body)
    user_match = Instagram.IG_USER_REGEX.search(yassibenitez.body)
    assert user_match
    assert user_match.group(1) == 'yassibenitez'
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(yassibenitez.body.strip())
    assert user_str_match
    assert user_str_match.group(1) == 'yassibenitez'

def test_instagram_matches_on_instagram_suffix(hanny_madani, kaja_sbn):
    assert not Instagram.IG_LINK_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(hanny_madani.body)
    assert not Instagram.IG_USER_REGEX.search(hanny_madani.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(hanny_madani.body.strip())
    assert user_str_match
    assert user_str_match.group(1) == 'Hanny_madani'
    assert not Instagram.IG_LINK_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_LINK_QUERY_REGEX.search(kaja_sbn.body)
    assert not Instagram.IG_USER_REGEX.search(kaja_sbn.body)
    user_str_match = Instagram.IG_USER_STRING_REGEX.search(kaja_sbn.body.strip())
    assert user_str_match
    assert user_str_match.group(1) == 'kaja_sbn'

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
    assert not Instagram.IG_USER_STRING_REGEX.search(on_insta_rant.body.strip())
    assert not Instagram.HAS_IG_KEYWORD_REGEX.search(on_insta_rant.body.strip())

