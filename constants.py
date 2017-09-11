import os
import sys
import urllib


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

DEFAULT_APP_NAME = 'ig-highlights-bot'
CONFIG_ROOT_DIR = os.path.join(CONFIG_ROOT_DIR, DEFAULT_APP_NAME)
DATA_ROOT_DIR = os.path.join(HOME, DEFAULT_APP_NAME)

ROOT_DIR = os.path.dirname( os.path.realpath(os.path.abspath(__file__)) )
BLACKLIST_DEFAULTS_PATH = os.path.join(ROOT_DIR, 'BLACKLIST')

AUTHOR = 'lv10wizard'
COMPOSE_MESSAGE_BASE_URL = 'https://www.reddit.com/message/compose/'
CONTACT_URL_FMT = (
        COMPOSE_MESSAGE_BASE_URL
        + '?to='
        + AUTHOR
        + '&subject={subject}'
)
BLACKLIST_SUBJECT = urllib.quote('BLACKLIST ME')
BLACKLIST_URL_FMT = (
        COMPOSE_MESSAGE_BASE_URL
        + '?to={to}&subject='
        + BLACKLIST_SUBJECT
)
REPO_URL = 'https://github.com/lv10wizard/ig-highlights-bot'
HELP_URL = '' # TODO

