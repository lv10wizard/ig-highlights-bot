# -*- coding: UTF-8 -*-
import pickle
import os
import pytest

from ..conftest import load_pickle


@pytest.fixture(scope='session')
def automoderator_user_link():
    """
    praw.models.Comment posted by AutoModerator containing an instagram
    user link
    """
    return load_pickle('automoderator')

@pytest.fixture(scope='session')
def linstahh():
    """ praw.models.Comment containing a soft-linked instagram user """
    return load_pickle('linstahh')

@pytest.fixture(scope='session')
def natalieannworth():
    """ praw.models.Comment containing a soft-linked instagram user """
    return load_pickle('natalieannworth')

@pytest.fixture(scope='session')
def tiffanie_marie():
    """ praw.models.Comment containing a soft-linked instagram user """
    return load_pickle('tiffanie.marie')

@pytest.fixture(scope='session')
def haileypandolfi():
    """ praw.models.Comment containing a hard-linked instagram user """
    return load_pickle('haileypandolfi')

@pytest.fixture(scope='session')
def viktoria_kay():
    """ praw.models.Comment containing a hard-linked instagram user """
    return load_pickle('viktoria_kay')

@pytest.fixture(scope='session')
def ig_media_link():
    """ praw.models.Comment containing a instagram media link """
    return load_pickle('medialink')

@pytest.fixture(scope='session')
def ig_media_link_no_trailing_slash():
    """
    praw.models.Comment containing a instagram media link with no trailing slash
    """
    return load_pickle('medialink_notrailingslash')

@pytest.fixture(scope='session')
def parenthesis_user():
    """
    praw.models.Comment posted by AutoModerator containing a soft-linked user
    """
    return load_pickle('parenthesis_user')

@pytest.fixture(scope='session')
def yassibenitez():
    """
    praw.models.Comment containing a soft-linked user (IG: ...)
    """
    return load_pickle('yassibenitez')

@pytest.fixture(scope='session')
def coffeequeennn():
    """
    praw.models.Comment containing a soft-linked user (IG: ...)
    """
    return load_pickle('coffeequeennn')

@pytest.fixture(scope='session')
def triippyunicorn():
    """
    praw.models.Comment containing a soft-linked user
    (Source: ig ...)
    """
    return load_pickle('triippyunicorn')

@pytest.fixture(scope='session')
def sugarnatty88():
    """
    praw.models.Comment containing a soft-linked user
    (IG - ...)
    """
    return load_pickle('sugarnatty88')

@pytest.fixture(scope='session')
def nachosarah():
    """
    praw.models.Comment containing a soft-linked user

    Instagram name: nachosarah... not yo Sarah.
    I wish she WAS my Sarah.

    """
    return load_pickle('nachosarah')

@pytest.fixture(scope='session')
def vyvan_le():
    """
    praw.models.Comment containing a soft-linked user without '@'
    """
    return load_pickle('vyvan.le')

@pytest.fixture(scope='session')
def stephxohaven():
    """
    praw.models.Comment containing a soft-linked user without '@'
    (... on instagram and snap)
    """
    return load_pickle('stephxohaven')

@pytest.fixture(scope='session')
def hanny_madani():
    """
    praw.models.Comment containing a soft-linked user without '@'
    (... on instagram)
    """
    return load_pickle('hanny_madani')

@pytest.fixture(scope='session')
def kaja_sbn():
    """
    praw.models.Comment containing a soft-linked user without '@'
    (... on instagram)
    """
    return load_pickle('kaja_sbn')

@pytest.fixture(scope='session')
def eva_lo_dimelo():
    """
    praw.models.Comment containing a soft-linked user without '@' (... on IG)
    """
    return load_pickle('eva_lo_dimelo')

@pytest.fixture(scope='session')
def chaileeson():
    """
    praw.models.Comment containing a soft-linked user without '@' (... on instagram)
    """
    return load_pickle('chaileeson')

@pytest.fixture(scope='session')
def deliahatesyou():
    """
    praw.models.Comment containing a soft-linked user without '@' (... (IG))
    """
    return load_pickle('deliahatesyou')

@pytest.fixture(scope='session')
def diablo_sam():
    """
    praw.models.Comment containing a soft-linked user without '@'
    (... on IG. ...)
    """
    return load_pickle('Diablo_sam')

@pytest.fixture(scope='session')
def alica_davis():
    """
    praw.models.Comment containing a soft-linked user without '@'
    (@... on IG ...)
    """
    return load_pickle('alica.davis')

@pytest.fixture(scope='session')
def fullmetalifrit_markdownlink():
    """
    praw.models.Comment containing a soft-linked user without '@'
    ([Fullmetalifrit on IG](...))
    """
    return load_pickle('fullmetalifrit_markdownlink')

@pytest.fixture(scope='session')
def capbarista_multiline_prefix():
    """
    praw.models.Comment containing a soft-linked user without '@'
    (IG: ...)
    """
    return load_pickle('capbarista_multiline_prefix')

@pytest.fixture(scope='session')
def multiline_random():
    """
    praw.models.Comment containing non-instagram related multiline text
    """
    return load_pickle('multiline_random')

@pytest.fixture(scope='session')
def multiline_single_word_usernames():
    """
    praw.models.Comment containing multiple instagram usernames:

    morganlux
    ladybug__espresso
    asdfasdfasdf
    fullmetalifrit
    blond.dieee
    """
    return load_pickle('multiline_single_word_usernames')

@pytest.fixture(scope='session')
def jessicabolusi_medialink():
    """
    praw.models.Comment containing an instagram media link with a user profile
    defined in its query
    """
    return load_pickle('jessicabolusi_medialink')

@pytest.fixture(scope='session')
def thanks_():
    """
    praw.models.Comment containing the word 'Thanks'
    """
    return load_pickle('thanks')

@pytest.fixture(scope='session')
def youre_():
    """
    praw.models.Comment containing the word 'You\'re'
    """
    return load_pickle('youre')

@pytest.fixture(scope='session')
def perfection_():
    """
    praw.models.Comment containing the word 'Perfection.'
    """
    return load_pickle('perfection')

@pytest.fixture(scope='session')
def whosethat():
    """
    praw.models.Comment containing the string 'Who is that?'
    """
    return load_pickle('whosethat')

@pytest.fixture(scope='session')
def on_insta_rant():
    """
    praw.models.Comment rant containing the string 'on Insta'
    """
    return load_pickle('on_insta_rant')

@pytest.fixture(scope='session')
def post_based_dawg_ireddit():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Based dawg'
    """
    return load_pickle('post_based_dawg_ireddit')

@pytest.fixture(scope='session')
def post_poor_hank_imgur():
    """
    praw.models.Submission linking to non-instagram content with the title
    'poor hank'
    """
    return load_pickle('post_poor_hank_imgur')

@pytest.fixture(scope='session')
def post_sju_gfycat():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Sara Jean Underwood'
    """
    return load_pickle('post_sju_gfycat')

@pytest.fixture(scope='session')
def selfpost_warm_welcome():
    """
    praw.models.Submission self-post with the title 'warm welcome'
    and the following text:

    Some migrants have arrived.
    Ushat stayed outside with a blue flashing "!".
    "Death is all around us. The horror..."
    "She is horrified after seeing the cyclops Rusna Powerlantern the Amber of Paint die."
    horrified by a 20 year old skeleton next to my entrance. this is going to be fun

    """
    return load_pickle('selfpost_warm_welcome')

@pytest.fixture(scope='session')
def post_pussy_slip_imgur():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Pussy slip' with comments containing instagram soft- and hard-links
    """
    return load_pickle('post_pussy_slip_imgur')

@pytest.fixture(scope='session')
def post_jamie_ig_imgur():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Jamie (IG: @jamie_baristaxo) at Hillbilly Hotties Silver Lake in Everett, WA'
    """
    return load_pickle('post_jamie_ig_imgur')

@pytest.fixture(scope='session')
def post_lenabarista_imgur():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Lena.barista'
    """
    return load_pickle('post_lenabarista_imgur')

@pytest.fixture(scope='session')
def post_deliahatesyou_ig_imgur():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Deliahatesyou (IG)'
    """
    return load_pickle('post_deliahatesyou_ig_imgur')

@pytest.fixture(scope='session')
def post_katiesintheclouds_ig_imgur():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Katiesintheclouds (IG)'
    """
    return load_pickle('post_katiesintheclouds_ig_imgur')

@pytest.fixture(scope='session')
def post_coffeecutie_beachvibes_imgur():
    """
    praw.models.Submission linking to non-instagram content with the title
    '@_coffeecutie #beachvibes [MIC]'
    """
    return load_pickle('post_coffeecutie_beachvibes_imgur')

@pytest.fixture(scope='session')
def post_multi_ats():
    """
    praw.models.Submission linking to non-instagram content with the title
    '@cheyannalavonzubas Last night’s attire for @inthismomentofficial @omandm
    and @avatarmetal 🤘🏻'
    """
    return load_pickle('post_multi_ats')

@pytest.fixture(scope='session')
def post_ig_url_in_title():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Top half a bit...young, bottom half all woman '
    '(nikumikyo, insta: https://www.instagram.com/nikumikyo/)'
    """
    return load_pickle('post_nikumikyo')

@pytest.fixture(scope='session')
def post_meow():
    """
    praw.models.Submission linking to non-instagram content with the title
    'Meow'
    """
    return load_pickle('post_meow')

