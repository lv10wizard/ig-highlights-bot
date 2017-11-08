import re


# the max number of requests that can be made before rate-limiting is
# imposed (this is a rolling limit per max_age, eg. 3000 / hr)
# XXX: I don't think this should be a config option since the user shouldn't
# be allowed to change this to any number they wish
RATELIMIT_THRESHOLD = 1000

BASE_URL_VARIATIONS = [
        'instagram.com',
        'instagr.am',

        # random web interface(s) to instagram
        'instaliga.com',
        'picbear.com',
        'vibbi.com',
        'yotagram.com',
        'yooying.com',
]
BASE_URL = BASE_URL_VARIATIONS[0]

# https://stackoverflow.com/a/33783840
# XXX: the media endpoint seems to be shutdown as of Nov 7, 2017
MEDIA_ENDPOINT = 'https://www.{0}/{{0}}/media'.format(BASE_URL)
META_ENDPOINT = 'https://www.{0}/{{0}}/?__a=1'.format(BASE_URL)
MEDIA_LINK_FMT = 'https://www.{0}/p/{{0}}'.format(BASE_URL)

# https://stackoverflow.com/a/17087528
# "30 symbols ... only letters, numbers, periods, and underscores"
# not sure if information is outdated
# XXX: periods cannot appear consecutively
# eg. 'foo.b.a.r' is ok; 'foo..bar' is not
# XXX: periods cannot appear as the first character nor the last character
_VALID_CHARS = '0-9A-Za-z_'
USERNAME_PTN = r'[{0}](?!.*[.]{{2,}})[{0}\.]{{,29}}(?<![.])'.format(
#                  |  \_____________/\____________/\______/
#                  |        |              |          /
#                  |        |              |    don't match if ends with '.'
#                  |        |      match 0-29 valid characters
#                  |     do not match if there are any consecutive periods
#               first character must be a letter, number, or underscore

        _VALID_CHARS,
)

_BASE_URL_PTN = r'https?://(?:www[.])?(?:{0})'.format('|'.join(
#                 \_______/\_________/\_____/
#                     |         |        \
#                     |         |     match domain variants
#                     |     optionally match leading 'www.'
#                   match scheme 'http://' or 'https://'

    BASE_URL_VARIATIONS
))

_MEDIA_PATH_PTN = r'p'
_MEDIA_CODE_PTN = r'[\w\-]{2,}'
IG_LINK_REGEX = re.compile(
        r'(?P<url>'
        # \______/
        #     \
        #   capture the entire match as 'url'
        r'(?P<baseurl>{0})/(?P<user>{1})(?!/{2}/?)(?:/[?].+)?'
        # \______________/|\___________/\________/\_________/
        #         |       |      |          |           \
        #         |       |      |          |      optionally match
        #         |       |      |          |         trailing queries
        #         |       |      |    don't match if this is a media code
        #         |       |      /
        #         |       |  capture username
        #         |       match path separator '/'
        #       capture base url
        r')'.format(
        # \
        # end of 'url' group

            _BASE_URL_PTN,
            USERNAME_PTN,
            _MEDIA_CODE_PTN,
        ),
        flags=re.IGNORECASE,
)

IG_LINK_QUERY_REGEX = re.compile(
        r'(?P<url>'
        # \______/
        #     \
        #   capture entire match as 'url' group
        r'(?P<baseurl>{0})/{1}/{2}/[?].*?taken-by=(?P<user>{3}).*$'
        # \______________/ \_/ \_/  | \__________________________/
        #         |         |   |   |             \
        #         |         |   |   |  match query string & capture
        #         |         |   |   |  taken-by username as 'user'
        #         |         |   |  match '?'
        #         |         |  match media code eg. 'BL7JX3LgxQ'
        #         |       match media code path
        #       capture base url
        r')'.format(
        # \
        # end of 'url' group

            _BASE_URL_PTN,
            _MEDIA_PATH_PTN,
            _MEDIA_CODE_PTN,
            USERNAME_PTN,
        ),
)

IG_AT_USER_REGEX = re.compile(
        r'(?:^|\s*(?<!\w)|[(\[])@(?P<user>{0})(?:[)\]]|\s+|$)'.format(
        #    | \________/ \___/ |\___________/\_____________/
        #    |     |        /   |      |             /
        #    |     |        \   |      |    match whitespace or end of string
        #    |     |        /   |      |    or set of acceptable ending
        #    |     |        \   |      |    delimiters
        #    |     |        /   |  capture username
        #    |     |        \   |  capture username
        #    |     |        /  only match if username is preceded by '@'
        #    |     |     allow valid set of leading characters
        #    |   allow 0+ leading whitespace so long as it is not preceded by
        #    |   a word-character
        #  match start of string

            USERNAME_PTN,
        ),
        flags=re.IGNORECASE,
)

_INSTAGRAM_KEYWORD = r'(?:insta(?:gram)?|ig)'
#                         \____________/  \
#                               |       match 'ig'
#                           match 'insta' or 'instagram'

_INSTAGRAM_KEYWORD_SEP = r'\s*[\:\-]'

# _IG_KEYWORD*: strings that are likely to indicate that the inner substring
# contains an instagram username.
_IG_KEYWORD_PREFIX = [
        # match eg. '(IG): ', 'insta ', etc
        r'\(?{0}\)?{1}?\s*'.format(
        #    \_/   \__/\_/
        #     |     /   |
        #     |     \ optionally match any spaces
        #     |   optionally match separators eg. ':'
        #    match instagram keywords
            _INSTAGRAM_KEYWORD, _INSTAGRAM_KEYWORD_SEP,
        ),

        # match eg. 'I think this is their instagram ...'
        #       or  'Her instagram name: ...'
        r'(?:[\w:]+\s+)*{0}(?:\s+\w+)*?{1}?\s+'.format(
        # \____________/\_/\__________/\__/  \
        #       |        |      |       / match trailing spaces
        #       |        |      |   optionally match separators eg. ':'
        #       |        |   match any extra words
        #       |      match instagram keywords
        #    match any leading words; include ':' in case of something like
        #       'Here: ...'
            _INSTAGRAM_KEYWORD, _INSTAGRAM_KEYWORD_SEP,
        ),
]
_IG_KEYWORD_PREFIX = '|'.join(_IG_KEYWORD_PREFIX)

_IG_KEYWORD_SUFFIX = r'\s+(?:on\s+{0}|\({0}\))[!.]?'.format(
#                         \_________/ \______/\___/
#                              |         |      \
#                              |         |  optionally match '!' or '.'
#                              |     match eg. '(IG)'
#                         match ' on instagram'
        _INSTAGRAM_KEYWORD,
)
_IG_KEYWORD_SUFFIX_VALID_ENDING_CHARS = r'[\?\]]'

HAS_IG_KEYWORD_REGEX = re.compile(
        '(?:(?:^|\s+){0}|\s*{1}(?:\s*\]|\s+|$))'.format(
        #   \__________/ \___________________/
        #        |                /
        #        |            match instagram keyword suffix
        #      match instagram keyword prefix
            _IG_KEYWORD_PREFIX,
            _IG_KEYWORD_SUFFIX,
        ),
        flags=re.IGNORECASE,
)

IG_USER_STRING_REGEX = [
        # XXX: try suffix first because the prefix regex canabalizes the
        # suffix regex
        # match a suffixed potential instagram username
        # eg. 'this is foobar on insta'
        r'(?:^|\s+|\[\s*)@?(?P<suffix>{0})(?:{1})(?:\s*{2}\s*|\s+|$)'.format(
        # \_____________/\_______________/\_____/\_________________/
        #        |               |           |         \
        #        |               |           |   only match if at the end of the
        #        |               |           |     string or followed by spaces
        #        |               |           |     or set of valid characters
        #        |               |           |
        #        |               |         match instagram keywords suffix
        #        |        capture possible username string
        #      only match if at the beginning of the string or preceded by
        #       spaces or markdown link text
            USERNAME_PTN,
            _IG_KEYWORD_SUFFIX,
            _IG_KEYWORD_SUFFIX_VALID_ENDING_CHARS,
        ),

        # match a prefixed potential instagram username
        # eg. 'IG: foobar'
        r'(?:^|\s+)(?:{1})@?(?P<prefix>{0})$'.format(
        # \_______/\_____/\_______________/ \
        #     |   |           |       only match if at the end of string
        #     |   |        capture possible username string
        #     / match instagram keywords prefix
        #   only match if at the beginning of the string
            USERNAME_PTN, _IG_KEYWORD_PREFIX,
        ),

        # match a possible instagram username if it is the only word
        r'^(?P<guess>{0})$'.format(USERNAME_PTN),
        # |\____________/ \
        # |      |       only match entire word
        # \    capture possible username string
        # only match entire word
]
IG_USER_STRING_REGEX = re.compile(
        '|'.join(IG_USER_STRING_REGEX),
        flags=re.IGNORECASE,
)

