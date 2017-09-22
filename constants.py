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

HOME = None
if sys.platform == 'win32':
    # windows
    # XXX: just let errors terminate the program because fuck windows
    CONFIG_ROOT_DIR = os.environ['APPDATA']
    HOME = os.environ['USERPROFILE']

elif sys.platform == 'darwin':
    # https://stackoverflow.com/a/3376074
    CONFIG_ROOT_DIR = '~/Library/Application Support'

else:
    # linux / cygwin / other
    try:
        CONFIG_ROOT_DIR = os.environ['XDG_CONFIG_HOME']
    except KeyError:
        CONFIG_ROOT_DIR = '~/.config'

if not HOME:
    HOME = '~'

DEFAULT_APP_NAME = 'igHighlightsBot'
CONFIG_ROOT_DIR = os.path.join(CONFIG_ROOT_DIR, DEFAULT_APP_NAME)
DATA_ROOT_DIR = os.path.join(HOME, DEFAULT_APP_NAME)

BLACKLIST_DEFAULTS_PATH = os.path.join(ROOT_DIR, 'BLACKLIST')
SUBREDDITS_DEFAULTS_PATH = os.path.join(ROOT_DIR, 'SUBREDDITS')

AUTHOR = 'lv10wizard'
COMPOSE_MESSAGE_BASE_URL = 'https://www.reddit.com/message/compose/'
CONTACT_SUBJECT_SKELETON = 'Instagram highlights bot'
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
)
REPO_URL = 'https://github.com/lv10wizard/ig-highlights-bot'
HELP_URL = '' # TODO

PREFIX_SUBREDDIT = 'r/'
PREFIX_USER = 'u/'

