import os
import sys

from six.moves.urllib.parse import quote


ROOT_DIR = os.path.dirname( os.path.realpath(os.path.abspath(__file__)) )
# hard-coded debug flag to switch some more spammy debug logging
__DEBUG__ = os.path.exists(os.path.join(ROOT_DIR, '__DEBUG__'))

class NoEmailSpecified(Exception): pass

EMAIL_PATH = os.path.join(ROOT_DIR, 'EMAIL')
try:
    with open(EMAIL_PATH, 'r') as fd:
        EMAIL = fd.read().strip()
except (IOError, OSError):
    raise NoEmailSpecified(
            'Please specify the maintainer\'s email in the file'
            ' \'{0}\''.format(EMAIL_PATH)
    )

if sys.platform == 'win32':
    # windows
    # XXX: just let errors terminate the program because fuck windows
    CONFIG_ROOT_DIR = os.environ['APPDATA']
    DATA_ROOT_DIR = os.environ['APPDATA']
    RUNTIME_ROOT_DIR = os.environ['TMP']

else:
    try:
        CONFIG_ROOT_DIR = os.environ['XDG_CONFIG_HOME']
    except KeyError:
        CONFIG_ROOT_DIR = None
    if not CONFIG_ROOT_DIR:
        if sys.platform == 'darwin':
            # https://stackoverflow.com/a/5084892
            CONFIG_ROOT_DIR = '~/Library/Preferences'
        else:
            CONFIG_ROOT_DIR = '~/.config'

    try:
        DATA_ROOT_DIR = os.environ['XDG_DATA_HOME']
    except KeyError:
        DATA_ROOT_DIR = None
    if not DATA_ROOT_DIR:
        if sys.platform == 'darwin':
            DATA_ROOT_DIR = '~/Library/'
        else:
            DATA_ROOT_DIR = '~/.local/share'

    try:
        RUNTIME_ROOT_DIR = os.environ['XDG_RUNTIME_DIR']
    except KeyError:
        RUNTIME_ROOT_DIR = None
    if not RUNTIME_ROOT_DIR:
        RUNTIME_ROOT_DIR = '/tmp'

DEFAULT_APP_NAME = 'igHighlightsBot'
CONFIG_ROOT_DIR = os.path.join(CONFIG_ROOT_DIR, DEFAULT_APP_NAME)
DATA_ROOT_DIR = os.path.join(DATA_ROOT_DIR, DEFAULT_APP_NAME)
RUNTIME_ROOT_DIR = os.path.join(RUNTIME_ROOT_DIR, DEFAULT_APP_NAME)

CONFIG_DEFAULTS_PATH = os.path.join(ROOT_DIR, 'bot.cfg')
BLACKLIST_DEFAULTS_PATH = os.path.join(ROOT_DIR, 'BLACKLIST')
SUBREDDITS_DEFAULTS_PATH = os.path.join(ROOT_DIR, 'SUBREDDITS')
JARGON_DEFAULTS_PATH = os.path.join(ROOT_DIR, 'JARGON')
POKEMON_PATH = os.path.join(ROOT_DIR, 'POKEMON')
USER_POOL_PATH = os.path.join(ROOT_DIR, 'USER_POOL')

AUTHOR = 'lv10wizard'
HELP_URL = '/74dtgu'
COMPOSE_MESSAGE_BASE_URL = '/message/compose/'
THING_ID_PLACEHOLDER = '____THING_ID_PLACEHOLDER____'
CONTACT_SUBJECT_SKELETON = 'Instagram highlights bot ({0})'.format(
        THING_ID_PLACEHOLDER
)
CONTACT_URL_FMT = (
        COMPOSE_MESSAGE_BASE_URL
        + '?to='
        + AUTHOR
        + '&subject={subject}'
)
CONTACT_URL = CONTACT_URL_FMT.format(
        subject=quote(CONTACT_SUBJECT_SKELETON),
)
BLACKLIST_SUBJECT = 'BLACKLIST ME'
REMOVE_BLACKLIST_SUBJECT = 'UNBLACKLIST ME'
BLACKLIST_URL_FMT = (
        COMPOSE_MESSAGE_BASE_URL
        + '?to={to}&subject='
        + quote(BLACKLIST_SUBJECT)
        + '&message={0}'.format(quote(
            '[no message required]'
        ))
)
REPO_URL = 'https://github.com/lv10wizard/ig-highlights-bot'

PREFIX_SUBREDDIT = 'r/'
PREFIX_USER = 'u/'

dry_run = False

