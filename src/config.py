import ConfigParser as configparser
import errno
import os
import re
import sys

from utillib import logger

from constants import (
        CONFIG_ROOT_DIR,
        DATA_ROOT_DIR,
        DEFAULT_APP_NAME,
)


# ######################################################################
# key constants

APP_NAME                      = 'app_name'
PRAW_SITENAME                 = 'praw_sitename'

REPLIES_DB_PATH               = 'replies_db_path'
NUM_HIGHLIGHTS_PER_IG_USER    = 'num_highlights_per_ig_user'
MAX_REPLIES_PER_COMMENT       = 'max_replies_per_comment'
MAX_REPLIES_PER_POST          = 'max_replies_per_post'
MAX_REPLIES_IN_COMMENT_THREAD = 'max_replies_in_comment_thread'

BLACKLIST_DB_PATH             = 'blacklist_db_path'
BLACKLIST_TEMP_BAN_TIME       = 'blacklist_temp_ban_time'

MESSAGES_DB_PATH              = 'messages_db_path'

LOGGING_PATH                  = 'logging_path'

INSTAGRAM_DB_PATH             = 'instagram_db_path'

# ######################################################################

def resolve_path(path):
    return os.path.realpath( os.path.abspath( os.path.expanduser(path) ) )

def parse_time(time_str):
    """
    Parses a time string into seconds (float).
    Seconds are assumed if no unit is specified.

    eg. '4d' -> 4 * 24 * 60 * 60

    Returns a float (seconds)
            -1 if parsing failed
    """
    if isinstance(time_str, (int, long, float)):
        return float(time_str)

    if isinstance(time_str, basestring):
        try:
            return float(time_str)

        except (TypeError, ValueError):
            match = re.findall(r'(\d+(?:[.]\d+)?)\s*([{0}])'.format(
            #                    \______________/\_/\_____/
            #                            |        |    \
            #                            |        |  capture time unit
            #                            |      match any number of spaces
            #                            |          (including 0)
            #                    capture time amount
                ''.join(Config.TO_SECONDS.keys())
            ), time_str)

            if not match:
                raise InvalidTime(time_str)

            # do not allow duplicate units (eg. 3d4d)
            result = 0.0
            seen_units = set()
            try:
                for amt, unit in match:
                    if unit in seen_units:
                        logger.prepend_id(logger.warn, 'parse_time',
                                'Duplicate unit \'{unit}\' found'
                                ' in \'{time_str}\': skipping \'{amt}{unit}\'',
                                unit=unit,
                                time_str=time_str,
                                amt=amt,
                        )

                    else:
                        result += (float(amt) * Config.TO_SECONDS[unit])
                        seen_units.add(unit)

            except KeyError as e:
                logger.prepend_id(logger.error, 'parse_time',
                        'Unrecognized time unit: \'{unit}\''
                        ' in \'{time_str}\'', e,
                        unit=unit,
                        time_str=time_str,
                )
                raise InvalidTime(time_str)

            else:
                return result

# ######################################################################

class InvalidTime(Exception): pass

class Config(object):
    """
    """

    SECTION = 'DEFAULT'
    PATH = os.path.join(CONFIG_ROOT_DIR, 'bot.cfg')

    # XXX: this does not account for leap seconds/years and assumes all months
    # are 30 days.
    TO_SECONDS = {
            's': 1,
            'm': 60,
            'h': 60 * 60,
            'd': 24 * 60 * 60,
            'w': 7 * 24 * 60 * 60,
            'M': 30 * 24 * 60 * 60,
            'Y': 365 * 24 * 60 * 60,
    }

    @property
    def __defaults(self):
        return {
                # the application name
                APP_NAME: DEFAULT_APP_NAME,

                # the sitename (section) in praw.ini to use
                PRAW_SITENAME: DEFAULT_APP_NAME,

                # path to the replies database file
                REPLIES_DB_PATH: os.path.join(DATA_ROOT_DIR, 'replies.db'),

                # the number of media to link per instagram user (per reply)
                # (ie, the number of highlights to reply with)
                NUM_HIGHLIGHTS_PER_IG_USER: '15',

                # max number of replies that can be made to the same comment
                # (in the event that a reply is > COMMENT_CHARACTER_LIMIT)
                MAX_REPLIES_PER_COMMENT: '1',

                # max number of total replies that can be made to the same post
                MAX_REPLIES_PER_POST: '5',

                # max number of replies in the same comment thread
                # (in the event that a user replies to a child of a bot's reply
                #  with reply-spawning text)
                # -- this is to prevent an infinite bot reply loop
                MAX_REPLIES_IN_COMMENT_THREAD: '3',

                # path to the blacklist database file
                BLACKLIST_DB_PATH: os.path.join(DATA_ROOT_DIR, 'blacklist.db'),

                # the amount of time temp bans last (see parse_time)
                BLACKLIST_TEMP_BAN_TIME: '4d',

                # path to the database file storing processed messages
                MESSAGES_DB_PATH: os.path.join(DATA_ROOT_DIR, 'messages.db'),

                # the path where log files are stored
                LOGGING_PATH: os.path.join(DATA_ROOT_DIR, 'logs'),

                # path to the instagram database file
                INSTAGRAM_DB_PATH: os.path.join(DATA_ROOT_DIR, 'instagram.db'),
        }

    def __init__(self):
        self.__parser = configparser.SafeConfigParser(self.__defaults)
        self._load()

    def __str__(self):
        return os.path.basename(Config.PATH)

    def _load(self):
        """
        Attempts to load the config file. Creates the default config file if
        it does not exist.
        """
        resolved_path = resolve_path(Config.PATH)
        if not os.path.exists(resolved_path):
            logger.prepend_id(logger.debug, self,
                    'Creating directories in \'{path}\'',
                    path=os.path.dirname(resolved_path),
            )
            try:
                os.makedirs( os.path.dirname(resolved_path) )

            except OSError as e:
                if e.errno == errno.EEXIST:
                    pass

            logger.prepend_id(logger.info, self,
                    'Writing default config to \'{path}\'',
                    path=Config.PATH,
            )
            # just let any errors through -- no config file should be fatal
            # (maybe)
            self.__write()

        else:
            logger.prepend_id(logger.info, self,
                    'Loading config from \'{path}\'',
                    path=Config.PATH,
            )
            with open(resolved_path, 'rb') as fd:
                self.__parser.readfp(fd)
            # write the settings back in case the file is missing any
            # Note: this will effectively wipe any deletions the user has made
            # to the file
            self.__write()

    def __write(self):
        resolved_path = resolve_path(Config.PATH)
        with open(resolved_path, 'wb') as fd:
            self.__parser.write(fd)

    def __handle_bad_val(self, key, err):
        value = self.__parser.get(Config.SECTION, key)
        default = self.__defaults[key]

        logger.prepend_id(logger.error, self,
                'Invalid value for \'{key}\': \'{value}\'.'
                ' Setting to default ({default})', err,
                key=key,
                value=value,
                default=default,
        )

        self.__parser.set(Config.SECTION, key, default)
        self.__write()

    def __get_path(self, key):
        try:
            path = self.__parser.get(Config.SECTION, key)

        # catch-all.. not great but I'm not sure what errors can be thrown
        except Exception as e:
            self.__handle_bad_val(key, e)
            path = self.__parser.get(Config.SECTION, key)

        return path

    def __get_path_resolved(self, key):
        return resolve_path(self.__get_path(key))

    def __get_path_raw(self, key):
        return self.__get_path(key)

    def __get_int(self, key):
        try:
            num = self.__parser.getint(Config.SECTION, key)

        except (TypeError, ValueError) as e:
            self.__handle_bad_val(key, e)
            num = self.__parser.getint(Config.SECTION, key)

        return num

    def __get_time(self, key):
        time_str = self.__parser.get(Config.SECTION, key)
        try:
            seconds = parse_time(time_str)

        except InvalidTime as e:
            self.__handle_bad_val(key, e)
            time_str = self.__parser.get(Config.SECTION, key)
            seconds = parse_time(time_str)

        return seconds

    @property
    def app_name(self):
        return self.__parser.get(Config.SECTION, APP_NAME)

    @property
    def praw_sitename(self):
        return self.__parser.get(Config.SECTION, PRAW_SITENAME)

    @property
    def replies_db_path(self):
        return self.__get_path_resolved(REPLIES_DB_PATH)

    @property
    def replies_db_path_raw(self):
        return self.__get_path_raw(REPLIES_DB_PATH)

    @property
    def num_highlights_per_ig_user(self):
        return self.__get_int(NUM_HIGHLIGHTS_PER_IG_USER)

    @property
    def max_replies_per_comment(self):
        return self.__get_int(MAX_REPLIES_PER_COMMENT)

    @property
    def max_replies_per_post(self):
        return self.__get_int(MAX_REPLIES_PER_POST)

    @property
    def max_replies_in_comment_thread(self):
        return self.__get_int(MAX_REPLIES_IN_COMMENT_THREAD)

    @property
    def blacklist_db_path(self):
        return self.__get_path_resolved(BLACKLIST_DB_PATH)

    @property
    def blacklist_db_path_raw(self):
        return self.__get_path_raw(BLACKLIST_DB_PATH)

    @property
    def blacklist_temp_ban_time(self):
        return self.__get_time(BLACKLIST_TEMP_BAN_TIME)

    @property
    def messages_db_path(self):
        return self.__get_path_resolved(MESSAGES_DB_PATH)

    @property
    def messages_db_path_raw(self):
        return self.__get_path_raw(MESSAGES_DB_PATH)

    @property
    def logging_path(self):
        return self.__get_path_resolved(LOGGING_PATH)

    @property
    def logging_path_raw(self):
        return self.__get_path_raw(LOGGING_PATH)

    @property
    def instagram_db_path(self):
        return self.__get_path_resolved(INSTAGRAM_DB_PATH)

    @property
    def instagram_db_path_raw(self):
        return self.__get_path_raw(INSTAGRAM_DB_PATH)


__all__ = [
        'resolve_path',
        'parse_time',
        'InvalidTime',
        'Config',
]

