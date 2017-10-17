import praw
import pytest

from src.replies import Parser


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
    'HnnNNNGGG', 'Whoosh', 'wHOooOoosh', 'Gatdaaaamn', 'Ooorah', 'Hoohrah',
    'Woahhhohoho', 'Woahhahahah', 'huehuehue', 'hueheuehuhheuheu',
    'Beeyooteafull', 'bEeeauutiiifuuul', 'xoxoxoox', 'homie...', 'automata',
    'selfie', 'selfey', 'selfy', 'pelfie', 'jeeebus', 'JEEESUS!', 'jesuscrhist',
    'jesuschirst', 'beeyotch', 'photoshop', 'shopt', 'shooopped', 'shoppedddd',
    'selfshot', 'Wowzie', 'wowzzeeyyyz', 'Bombsss', 'bommmbbb', 'biergarten',
    'oktoberfest', 'oooooctoberfeesssttt', 'dirndl', 'dirdnl', 'drindl',
    'dridnl', 'sideboob', 'rearpussy', 'asshooole', 'diiiick', 'PEEENIS',
    'downblouse', 'boooobieesss', 'boooobs', 'boob', 'buuuttts', 'butts',
    'buttockssss', 'frontbutt', 'frontasss', 'pussyyyy', 'upskirtttt',
    'upshort', 'upshooooorts', 'underboobs', 'underbooobies', 'sidebooobies',
    'ahueheuheuhhehu', 'UHEUAHEUEHAHUEHAUEH', 'booooty', 'whooty', 'paag',
    'pawg', 'yeezys', 'fuccboi', 'fukboi', 'fuckboy', 'fuqboeeeeyy', 'hoooot',
    'hawwwwt', 'hotttie', 'hottey', 'hottyyy', 'hotties', 'hawwwtieee',
    'booobage', 'oopsie', 'oooopsy', 'oopsey', 'oopsies', 'spammmmmm',
    'suuuperrr!', 'superman', 'superb0i', 'superboy', 'superwoman',
    'superwomen', 'supermen', 'suprrrrr', 'supergrrrrl', 'supergirl',
    'ayyyyy', 'ayyyyylmaorofl', 'lmaoayyyyy', 'REEEEEEEE', 'RRRREEEEEEEEEEE',
    'yummmm', 'yummyyyy', 'yumminesss', 'yummyness', 'yummmyyyynesssss',
    'yummies', 'hawwwtdayummm', 'hotdamn!', 'hawtdaaayuuumnnnn', 'holymoly',
    'hooolyyyyy', 'Bubblebut', 'bubbleeeee', 'bubbbbble', 'bubblebutttttt',
    'aappleboooty', 'applewhooties', 'bubblebooty', 'bhoottay', 'whoottayyy',
    'Heyoooo', 'ayyyyyooooo', 'heeeyyyyyy', 'waaaaaait', 'Heyo!', 'shiiiittt',
    'shhhhhhhit', 'shit', 'shiet', 'sheeeit', 'boooooo', 'bbbooooo',
    'motherfuuuuuhhhh', 'motherfuqqqqq', 'muthafuqqqqahhhh', 'motherfuckerrrr',
    'mothaaaafuckaaaa', 'mothrrrfuhhhckrrrrr', 'shaddup', 'shaattttup',
    'shutup', 'shuuuuutaahhhhhp', 'suckaaaaahhh', 'suckaaa', 'mothaasuckaaaa',
    'suqqqqquuuuhhhh', 'suckerrrr', 'awwwwhhh', 'ahhhhhhwwww', 'ahhhhh',
    'awwwwww', 'riiiiip', 'rrrriipppppppppp',
] + ['o'*(i+2) for i in range(15)])
def test_parser_detects_jargon(word):
    assert Parser.is_jargon(word)

@pytest.mark.parametrize('word', [
    'Daring', 'gorgeous', 'google', 'vyvan.le', 'Hanny_madani', 'kaja_sbn',
    'haileypandolfi', 'viktoria_kay', 'linstahh', 'natalieannworth',
    'tiffanie_marie', 'tiffanie.marie', 'jessicabolusi',
])
def test_parser_does_not_overmatch_jargon(word):
    assert not Parser.is_jargon(word)

def test_parser_init(
        linstahh, selfpost_warm_welcome, post_lenabarista_imgur,
        post_coffeecutie_beachvibes_imgur,
):
    L = Parser(linstahh)
    assert bool(L.thing)
    assert isinstance(L.thing, praw.models.Comment)

    W = Parser(selfpost_warm_welcome)
    assert bool(W.thing)
    assert isinstance(W.thing, praw.models.Submission)

    LB = Parser(post_lenabarista_imgur)
    assert bool(LB.thing)
    assert isinstance(LB.thing, praw.models.Submission)

    CC = Parser(post_coffeecutie_beachvibes_imgur)
    assert bool(CC.thing)
    assert isinstance(CC.thing, praw.models.Submission)

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

@pytest.mark.xfail # handled at the Filter level
def test_parser_ignores_automod(parenthesis_user, automoderator_user_link):
    P = Parser(parenthesis_user)
    assert not p.ig_links
    assert not p.ig_usernames

    A = Parser(automoderator_user_link)
    assert not A.ig_links
    assert not A.ig_usernames

def test_parser_matches_non_english_word(vyvan_le):
    p = Parser(vyvan_le)
    assert not p.ig_links
    assert p.ig_usernames == ['vyvan.le']

def test_parser_matches_instagram_prefix(
        yassibenitez, coffeequeennn, triippyunicorn,
):
    Y = Parser(yassibenitez)
    assert not Y.ig_links
    assert Y.ig_usernames == ['yassibenitez']

    C = Parser(coffeequeennn)
    assert not C.ig_links
    assert C.ig_usernames == ['_coffeequeennn']

    T = Parser(triippyunicorn)
    assert not T.ig_links
    assert T.ig_usernames == ['triippyunicorn']

def test_parser_matches_instagram_suffix(
        hanny_madani, kaja_sbn, eva_lo_dimelo, chaileeson, deliahatesyou,
        diablo_sam, stephxohaven,
):
    H = Parser(hanny_madani)
    assert not H.ig_links
    assert H.ig_usernames == ['Hanny_madani']

    K = Parser(kaja_sbn)
    assert not K.ig_links
    assert K.ig_usernames == ['kaja_sbn']

    E = Parser(eva_lo_dimelo)
    assert not E.ig_links
    assert E.ig_usernames == ['eva_lo_dimelo']

    C = Parser(chaileeson)
    assert not C.ig_links
    assert C.ig_usernames == ['chaileeson']

    D = Parser(deliahatesyou)
    assert not D.ig_links
    assert D.ig_usernames == ['Deliahatesyou']

    DS = Parser(diablo_sam)
    assert not DS.ig_links
    assert DS.ig_usernames == ['Diablo_sam']

    S = Parser(stephxohaven)
    assert not S.ig_links
    assert S.ig_usernames == ['stephxohaven']

def test_parser_matches_multiline_user_string(capbarista_multiline_prefix):
    C = Parser(capbarista_multiline_prefix)
    assert not C.ig_links
    assert C.ig_usernames == ['capbarista']

def test_parser_does_not_match_multiline_random_text(multiline_random):
    p = Parser(multiline_random)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_matches_user_linked_in_query(jessicabolusi_medialink):
    J = Parser(jessicabolusi_medialink)
    assert J.ig_links
    assert J.ig_usernames == ['jessicabolusi']

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

def test_parser_does_not_match_on_insta_rant(on_insta_rant):
    # '[...] him on Insta or facebook [...]'
    p = Parser(on_insta_rant)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_post_based_dawg(post_based_dawg_ireddit):
    # 'Based dawg'
    p = Parser(post_based_dawg_ireddit)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_post_poor_hank(post_poor_hank_imgur):
    # 'poor hank'
    p = Parser(post_poor_hank_imgur)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_post_sju(post_sju_gfycat):
    # 'Sara Jean Underwood'
    p = Parser(post_sju_gfycat)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_selfpost_warm_welcome(selfpost_warm_welcome):
    # 'warm welcome'
    p = Parser(selfpost_warm_welcome)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_not_match_post_pussy_slip(post_pussy_slip_imgur):
    # 'Pussy slip'
    p = Parser(post_pussy_slip_imgur)
    assert not p.ig_links
    assert not p.ig_usernames

def test_parser_does_match_post_jamie_ig(post_jamie_ig_imgur):
    # 'Jamie (IG: @jamie_baristaxo) at Hillbilly Hotties Silver Lake in Everett, WA'
    p = Parser(post_jamie_ig_imgur)
    assert not p.ig_links
    assert p.ig_usernames == ['jamie_baristaxo']

def test_parser_does_match_post_lenabarista(post_lenabarista_imgur):
    # 'Lena.barista'
    p = Parser(post_lenabarista_imgur)
    assert not p.ig_links
    assert p.ig_usernames == ['Lena.barista']

def test_parser_does_match_post_deliahatesyou_ig(post_deliahatesyou_ig_imgur):
    # 'Deliahatesyou (IG)'
    p = Parser(post_deliahatesyou_ig_imgur)
    assert not p.ig_links
    assert p.ig_usernames == ['Deliahatesyou']

def test_parser_does_match_post_katiesintheclouds_ig(post_katiesintheclouds_ig_imgur):
    # 'Katiesintheclouds (IG)'
    p = Parser(post_katiesintheclouds_ig_imgur)
    assert not p.ig_links
    assert p.ig_usernames == ['Katiesintheclouds']

def test_parser_does_match_post_coffeecutie_beachvibes(post_coffeecutie_beachvibes_imgur):
    # '@_coffeecutie #beachvibes [MIC]'
    p = Parser(post_coffeecutie_beachvibes_imgur)
    assert not p.ig_links
    assert p.ig_usernames == ['_coffeecutie']

