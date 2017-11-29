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
    'awwwwww', 'riiiiip', 'rrrriipppppppppp', 'oomph', 'oooomf', 'yowzers',
    'yowzas', 'yowsers', 'yowzerrrz', 'yowzah', 'riiiiight', 'rightttt',
    'rrrright', 'rrrriiiighhhhhtt', 'wronggg', 'wroooong', 'wwwrrrong',
    'lmaoh', 'ughhhhh', 'uuuuuugh', 'ugggggggh', 'uuuggggghhhhh', 'bulbasaur',
    'pikaaachuuuu', 'squirrrrtle', 'pleeeeease', 'ppppplease', 'pleaaaase',
    'pleaseeeee', 'plssss', 'puhleeezeeee', 'plaese', 'indeeeeed',
    'indeeeeeedddd', 'poleeeeze', 'pohleeease', 'saaweeeeet', 'sweeeeetttt',
    'suuuhhhweeeeet', 'belfie', 'pelfieeeee', 'selfieeeee', 'FAGGGGG',
    'FAAAAGGGGOOOOOTTTT', 'lesbooooos', 'lezzzzbooossss', 'lesbiiiiaannnnn',
    'perrrfect', 'perfeeeccct', 'perfectionnnn', 'purrrrfectioooon', 'dumbass',
    'dumbasssss', 'dumbassssshooooole', 'dumbassoles', 'asshooooooles',
    'dumbassholessss', 'dumbasses', 'hnrrrrhhhh', 'hrrruunngggrrrff', 'HRNH',
    'bwahahahah', 'bwwwahahahhaha', 'wahahhhaaaha', 'whoopah', 'gigady',
    'giggity', 'giggitygigittieee', 'ggiggittiiiieee', 'giggiteeeee',
    'gigggaddiiiii', 'creepshot', 'creeeeeeper', 'creeepy', 'creepcreepy',
    'diiiingus', 'trippy', 'trippppyyy', 'trrrripppeeeyyy', 'triiiippiiieee',
    'downvoted', 'upvoted', 'downvote', 'upvote', 'cutiepieee', 'qt3.14',
    'cutie3.14', 'qt3.14159265359', 'cutie3.14159265359', 'qtpie', 'goodie',
    'goody', 'gooooody', 'gooooodieieieie', 'goodiebag', 'goodiebaaaagggg',
    'bangin', 'banging', 'baaaaangin', 'banggggginggggg', 'xd', 'XD', 'XDDDD',
    'xdddddddddddddd', 'xxxdddddddddddddddddDDDdd', 'yummers', 'yummerzz',
    'gfycat', 'instagram', 'facebook', 'facebooooook', 'twitter', 'twitterrr',
    'verizon', 'comcast', 'myspace', 'myyyyspace', 'myspaaaace', 'youtube',
    'youtuuuube', 'pornhub', 'google', 'yahoo', 'yahooooo', 'microsoft',
    'bankofamerica', 'chase', 'safeway', 'kohls', 'pizzahut', 'tacobel',
    'tacobell', 'doritos', 'mountaindew', 'cocacola', 'coooke', 'pepsi',
    'pepsie', 'pepperidgefarm', 'vimeo', 'vidme', 'firefox', 'mozilla',
    'github', 'bitbucket', 'gmail', 'gmaaaaail', 'emaaaaail', 'reddit',
    'redddditttt', 'imgur', 'starbucks', 'peeeets', 'peetscoffee', 'costco',
    'samsclub', 'walmart', 'waaaaalmaaaaart', 'gamestop', 'netflix', 'hulu',
    'amazonprime', 'amazoooon', 'twitch', 'dailymotion', 'barnesandnoble',
    'barnesandnobles', 'urbanoutfitters', 'uniqlo', 'pacsun', 'lulus',
    'lululemon', 'lululemons', 'adidas', 'nike', 'americaneagle', 'levis',
    'redbubble', 'redtube', 'buzzfeed', 'kotaku', 'msnbc', 'foxnews',
    'hottopic', 'nytimes', 'washingtonpost', 'youporn',
] + ['o'*(i+2) for i in range(15)] + ['_'*(i+1) for i in range(20)])
def test_parser_detects_jargon(word):
    assert Parser.is_jargon(word)

@pytest.mark.parametrize('word', [
    'Daring', 'gorgeous', 'vyvan.le', 'hanny_madani', 'kaja_sbn',
    'haileypandolfi', 'viktoria_kay', 'linstahh', 'natalieannworth',
    'tiffanie_marie', 'tiffanie.marie', 'jessicabolusi', 'girl.6ix',
    '_cassiebrown_', '___foo__bar._._', '.blah', 'asdf____', '___asdf',
    'qwerty.', 'x_o_x_o_x',
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

def test_parser_matches_multiple_ats(post_multi_ats):
    M = Parser(post_multi_ats)
    assert not M.ig_links
    assert len(M.ig_usernames) == 4
    assert 'cheyannalavonzubas' in M.ig_usernames
    assert 'inthismomentofficial' in M.ig_usernames
    assert 'omandm' in M.ig_usernames
    assert 'avatarmetal' in M.ig_usernames

def test_parser_does_not_overmatch_at_user(
        melvinbrucefrench_email, throwawaymedic08_email,
):
    M = Parser(melvinbrucefrench_email)
    assert not M.ig_links
    assert not M.ig_usernames

    T = Parser(throwawaymedic08_email)
    assert not T.ig_links
    assert not T.ig_usernames

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
        yassibenitez, coffeequeennn, triippyunicorn, sugarnatty88,
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

    S = Parser(sugarnatty88)
    assert not S.ig_links
    assert S.ig_usernames == ['sugarnatty88']

def test_parser_does_not_over_match_prefix(nachosarah):
    N = Parser(nachosarah)
    assert not N.ig_links
    assert not N.ig_usernames

def test_parser_matches_instagram_suffix(
        hanny_madani, kaja_sbn, eva_lo_dimelo, chaileeson, deliahatesyou,
        diablo_sam, stephxohaven, fullmetalifrit_markdownlink,
):
    H = Parser(hanny_madani)
    assert not H.ig_links
    assert H.ig_usernames == ['hanny_madani']

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
    assert D.ig_usernames == ['deliahatesyou']

    DS = Parser(diablo_sam)
    assert not DS.ig_links
    assert DS.ig_usernames == ['diablo_sam']

    S = Parser(stephxohaven)
    assert not S.ig_links
    assert S.ig_usernames == ['stephxohaven']

    F = Parser(fullmetalifrit_markdownlink)
    assert not F.ig_links
    assert F.ig_usernames == ['fullmetalifrit']

def test_parser_matches_instagram_suffix_question(
        nikinikiii_question, mollyjcurley_question,
):
    N = Parser(nikinikiii_question)
    assert not N.ig_links
    assert N.ig_usernames == ['nikinikiii']

    M = Parser(mollyjcurley_question)
    assert not M.ig_links
    assert M.ig_usernames == ['mollyjcurley']

def test_parser_does_not_match_invalid_username(alica_davis):
    A = Parser(alica_davis)
    assert not A.ig_links
    assert not A.ig_usernames

def test_parser_guesses_quoted_user_string(karmabirdfly_quote):
    K = Parser(karmabirdfly_quote)
    assert not K.ig_links
    assert K.ig_usernames == ['karmabirdfly']

def test_parser_matches_bolded_at_ig_user(inezfulitko_markdown):
    I = Parser(inezfulitko_markdown)
    assert not I.ig_links
    assert I.ig_usernames == ['inezfulitko']

def test_parser_matches_ig_keyword_user_string_in_parenthesis(veronicabielik):
    V = Parser(veronicabielik)
    assert not V.ig_links
    assert V.ig_usernames == ['veronicabielik']

def test_parser_matches_multiline_user_string(capbarista_multiline_prefix):
    C = Parser(capbarista_multiline_prefix)
    assert not C.ig_links
    assert C.ig_usernames == ['capbarista']

def test_parser_matches_multiline_user_strings(multiline_single_word_usernames):
    M = Parser(multiline_single_word_usernames)
    assert not M.ig_links
    assert len(M.ig_usernames) == 5
    assert 'morganlux' in M.ig_usernames
    assert 'ladybug__espresso' in M.ig_usernames
    assert 'asdfasdfasdf' in M.ig_usernames
    assert 'fullmetalifrit' in M.ig_usernames
    assert 'blond.dieee' in M.ig_usernames

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
    assert p.ig_usernames == ['lena.barista']

def test_parser_does_match_post_deliahatesyou_ig(post_deliahatesyou_ig_imgur):
    # 'Deliahatesyou (IG)'
    p = Parser(post_deliahatesyou_ig_imgur)
    assert not p.ig_links
    assert p.ig_usernames == ['deliahatesyou']

def test_parser_does_match_post_katiesintheclouds_ig(post_katiesintheclouds_ig_imgur):
    # 'Katiesintheclouds (IG)'
    p = Parser(post_katiesintheclouds_ig_imgur)
    assert not p.ig_links
    assert p.ig_usernames == ['katiesintheclouds']

def test_parser_does_match_post_coffeecutie_beachvibes(post_coffeecutie_beachvibes_imgur):
    # '@_coffeecutie #beachvibes [MIC]'
    p = Parser(post_coffeecutie_beachvibes_imgur)
    assert not p.ig_links
    assert p.ig_usernames == ['_coffeecutie']

def test_parser_does_match_post_ig_url_in_title(post_ig_url_in_title):
    # '... (nikumikyo, insta: https://www.instagram.com/nikumikyo/)'
    p = Parser(post_ig_url_in_title)
    assert len(p.ig_links) == 1
    assert p.ig_usernames == ['nikumikyo']

def test_parser_does_match_post_meow(post_meow):
    # 'Meow'
    p = Parser(post_meow)
    assert not p.ig_links
    assert not p.ig_usernames

