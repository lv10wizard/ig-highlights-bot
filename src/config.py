import errno
import os
import re

from six import (
        string_types,
        integer_types,
)
from six.moves import configparser
from six.moves.configparser import (
        NoOptionError,
        NoSectionError,
)

from constants import (
        CONFIG_DEFAULTS_PATH,
        CONFIG_ROOT_DIR,
        DATA_ROOT_DIR,
)
from src.util import logger


# ######################################################################
# key constants

DATA_DIR                        = 'data_dir'

SECTION_PRAW                    = 'PRAW'
PRAW_SITENAME                   = 'praw_sitename'

SECTION_REDDIT                  = 'REDDIT'
APP_NAME                        = 'app_name'
SEND_DEBUG_PM                   = 'send_debug_pm'
NUM_HIGHLIGHTS_PER_IG_USER      = 'num_highlights_per_ig_user'
MAX_REPLIES_PER_COMMENT         = 'max_replies_per_comment'
MAX_REPLIES_PER_POST            = 'max_replies_per_post'
MAX_REPLIES_IN_COMMENT_THREAD   = 'max_replies_in_comment_thread'
DELETE_COMMENT_THRESHOLD        = 'delete_comment_threshold'
ADD_SUBREDDIT_THRESHOLD         = 'add_subreddit_threshold'
BLACKLIST_TEMP_BAN_TIME         = 'blacklist_temp_ban_time'
BAD_ACTOR_EXPIRE_TIME           = 'bad_actor_expire_time'
BAD_ACTOR_THRESHOLD             = 'bad_actor_threshold'

SECTION_INSTAGRAM               = 'INSTAGRAM'
INSTAGRAM_CACHE_EXPIRE_TIME     = 'instagram_cache_expire_time'

SECTION_LOGGING                 = 'LOGGING'
LOGGING_PATH                    = 'logging_path'
LOGGING_LEVEL                   = 'logging_level'
COLORFUL_LOGS                   = 'colorful_logs'

# ######################################################################

def resolve_path(path):
    if path:
        return os.path.realpath( os.path.abspath( os.path.expanduser(path) ) )
    return ''

def parse_time(time_str):
    """
    Parses a time string into seconds (float).
    Seconds are assumed if no unit is specified.

    eg. '4d' -> 4 * 24 * 60 * 60

    Returns a float (seconds)
            -1 if parsing failed
    """
    if isinstance(time_str, integer_types + (float,)):
        return float(time_str)

    if isinstance(time_str, string_types):
        match = None
        try:
            return float(time_str)

        except (TypeError, ValueError):
            match = re.findall(r'(\d+(?:[.]\d+)?)\s*([{0}]|$)'.format(
            #                    \______________/\_/\_______/
            #                            |        |      \
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
                    logger.id(logger.warn, 'parse_time',
                            'Duplicate unit \'{unit}\' found'
                            ' in \'{time_str}\': skipping \'{amt}{unit}\'',
                            unit=unit,
                            time_str=time_str,
                            amt=amt,
                    )

                else:
                    multiplier = 1
                    if unit:
                        multiplier = Config.TO_SECONDS[unit]
                    result += (float(amt) * multiplier)
                    seen_units.add(unit)

        except KeyError as e:
            logger.id(logger.exception, 'parse_time',
                    'Unrecognized time unit: \'{unit}\''
                    ' in \'{time_str}\'',
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
    Config handling (basically a configparser wrapper)
    """

    FILENAME = 'bot.cfg'
    PATH = os.path.join(CONFIG_ROOT_DIR, FILENAME)

    DEFAULTS = {
            DATA_DIR: DATA_ROOT_DIR,
    }

    # XXX: this does not account for leap seconds/years and assumes all months
    # are 30 days.
    TO_SECONDS = {
            ' ': 1,
            's': 1,
            'm': 60,
            'h': 60 * 60,
            'd': 24 * 60 * 60,
            'w': 7 * 24 * 60 * 60,
            'M': 30 * 24 * 60 * 60,
            'Y': 365 * 24 * 60 * 60,
    }

    def __init__(self, path=None):
        self.path = path or Config.PATH
        self._resolved_fallback = resolve_path(CONFIG_DEFAULTS_PATH)
        self._resolved_path = resolve_path(self.path)
        if not os.path.exists(os.path.dirname(self._resolved_path)):
            logger.id(logger.debug, self,
                    'Creating directories in \'{path}\' ...',
                    path=self.path,
            )
            try:
                os.makedirs(os.path.dirname(self._resolved_path))
            except OSError as e:
                if e.errno == errno.EEXIST:
                    pass
                else:
                    logger.id(logger.critical, self,
                            'Could not create config directories!'
                            ' (do you have proper permissions?)',
                            exc_info=True,
                    )
                    raise
        if os.path.isdir(self._resolved_path):
            # only the directory path was given: append the filename
            self.path = os.path.join(self.path, Config.FILENAME)
            self._resolved_path = os.path.join(
                    self._resolved_path, Config.FILENAME
            )

        self.__fallback = configparser.SafeConfigParser(Config.DEFAULTS)
        loaded = self.__fallback.read(self._resolved_fallback)
        fallback_was_loaded = self._resolved_fallback in loaded
        if not fallback_was_loaded:
            logger.id(logger.warn, self,
                    'Failed to load fallback config (\'{path}\'):'
                    ' bad/missing options may terminate the program.',
            )

        self.__parser = configparser.SafeConfigParser(Config.DEFAULTS)
        loaded = self.__parser.read(self._resolved_path)
        if self._resolved_path not in loaded:
            self.__parser = self.__fallback
            self.__do_write()

        elif fallback_was_loaded:
            # check for any missing/extra options
            changed = False
            fallback_sections = self.__fallback.sections()
            missing_sections = [
                    section for section in self.__parser.sections()
                    if section not in fallback_sections
            ]
            if missing_sections:
                changed = True
                logger.id(logger.debug, self,
                        'Removing missing sections: {color}',
                        color=missing_sections,
                )

            for section in missing_sections:
                if not self.__parser.remove(section):
                    # this shouldn't happen
                    logger.id(logger.warn, self,
                            'Failed to remove section [{section}]:'
                            ' no such section',
                            section=section,
                    )

            for section in fallback_sections:
                if not self.__parser.has_section(section):
                    logger.id(logger.debug, self,
                            'Adding new section: [{section}]',
                            section=section,
                    )
                    try:
                        self.__parser.add_section(section)
                    except ValueError:
                        # DEFAULT section (this shouldn't happen)
                        pass
                    else:
                        changed = True

                fallback_opts = self.__fallback.options(section)
                parser_opts = self.__parser.options(section)

                only_in_fallback = set(fallback_opts) - set(parser_opts)
                for key in only_in_fallback:
                    value = self.__fallback.get(section, key)
                    logger.id(logger.debug, self,
                            'Adding new option:'
                            ' [{section}] \'{key}\' -> \'{value}\'',
                            section=section,
                            key=key,
                            value=value,
                    )
                    self.__parser.set(section, key, value)

                only_in_parser = set(parser_opts) - set(fallback_opts)
                for key in only_in_parser:
                    value = self.__parser.get(section, key)
                    logger.id(logger.debug, self,
                            'Removing missing option:'
                            ' [{section}] \'{key}\' ({value})',
                            secttion=section,
                            key=key,
                            value=value,
                    )

                changed = changed or bool(only_in_fallback or only_in_fallback)

            if changed:
                # the user version had missing/extra options
                self.__do_write()

    def __str__(self):
        return os.path.basename(self.path)

    def __do_write(self):
        logger.id(logger.info, self,
                'Writing config to \'{path}\' ...',
                path=self.path,
        )
        success = False
        try:
            with open(self._resolved_path, 'w') as fd:
                self.__parser.write(fd)
        except (IOError, OSError):
            logger.id(logger.exception, self,
                    'Failed to write config to \'{path}\'',
                    path=self.path,
            )
        else:
            success = True

        return success

    def __get_fallback(self, section, key, err=None, get_func='get'):
        try:
            value = self.__parser.get(section, key)
        except NoSectionError:
            value = '<No section [{0}]>'.format(section)
        except NoOptionError:
            value = '<No Option [{0}]>'.format(key)
        except:
            value = '<???>'

        try:
            getter = getattr(self.__fallback, get_func)
        except AttributeError:
            getter = getattr(self.__fallback, 'get')
        default = getter(section, key)

        logger.id(logger.warn, self,
                'Invalid value for \'{key}\': {value}.'
                ' Using default: \'{default}\'',
                key=key,
                value=value,
                default=default,
                exc_info=err,
        )

        return default

    def __get(self, section, key, get_func='get'):
        # possible AttributeError if get_func has a typo
        getter = getattr(self.__parser, get_func)
        try:
            result = getter(section, key)
        except (NoOptionError, NoSectionError, ValueError) as e:
            result = self.__get_fallback(section, key, e, get_func)
        return result

    def __get_time(self, section, key):
        time_str = self.__parser.get(section, key)
        try:
            seconds = parse_time(time_str)
        except (NoOptionError, NoSectionError, InvalidTime) as e:
            time_str = self.__get_fallback(section, key)
            seconds = parse_time(time_str)
        return seconds

# ######################################################################

    # [PRAW]
    @property
    def praw_sitename(self):
        return self.__get(SECTION_PRAW, PRAW_SITENAME)

    # ##################################################################
    # [REDDIT]

    @property
    def app_name(self):
        return self.__get(SECTION_REDDIT, APP_NAME)

    @property
    def send_debug_pm(self):
        return self.__get(SECTION_REDDIT, SEND_DEBUG_PM, 'getboolean')

    @property
    def num_highlights_per_ig_user(self):
        return self.__get(SECTION_REDDIT, NUM_HIGHLIGHTS_PER_IG_USER, 'getint')

    @property
    def max_replies_per_comment(self):
        return self.__get(SECTION_REDDIT, MAX_REPLIES_PER_COMMENT, 'getint')

    @property
    def max_replies_per_post(self):
        return self.__get(SECTION_REDDIT, MAX_REPLIES_PER_POST, 'getint')

    @property
    def max_replies_in_comment_thread(self):
        return self.__get(
                SECTION_REDDIT, MAX_REPLIES_IN_COMMENT_THREAD, 'getint'
        )

    @property
    def delete_comment_threshold(self):
        return self.__get(SECTION_REDDIT, DELETE_COMMENT_THRESHOLD, 'getint')

    @property
    def add_subreddit_threshold(self):
        return self.__get(SECTION_REDDIT, ADD_SUBREDDIT_THRESHOLD, 'getint')

    @property
    def blacklist_temp_ban_time(self):
        return self.__get_time(SECTION_REDDIT, BLACKLIST_TEMP_BAN_TIME)

    @property
    def bad_actor_expire_time(self):
        return self.__get_time(SECTION_REDDIT, BAD_ACTOR_EXPIRE_TIME)

    @property
    def bad_actor_threshold(self):
        return self.__get(SECTION_REDDIT, BAD_ACTOR_THRESHOLD, 'getint')

    # ##################################################################
    # [INSTAGRAM]

    @property
    def instagram_cache_expire_time(self):
        return self.__get_time(SECTION_INSTAGRAM, INSTAGRAM_CACHE_EXPIRE_TIME)

    # ##################################################################
    # [LOGGING]

    @property
    def logging_path(self):
        return resolve_path(self.__get(SECTION_LOGGING, LOGGING_PATH))

    @property
    def logging_path_raw(self):
        return self.__get(SECTION_LOGGING, LOGGING_PATH)

    @property
    def logging_level(self):
        level = self.__get(SECTION_LOGGING, LOGGING_LEVEL)
        if isinstance(level, string_types):
            # test that the level name exists
            try:
                getattr(logger, level)
            except AttributeError:
                level = None
        elif not isinstance(level, integer_types):
            # not a valid logging level code
            level = None

        if not level:
            level = self.__get_fallback(SECTION_LOGGING, LOGGING_LEVEL)

        return level

    @property
    def colorful_logs(self):
        return self.__get(SECTION_LOGGING, COLORFUL_LOGS, 'getboolean')


__all__ = [
        'resolve_path',
        'parse_time',
        'InvalidTime',
        'Config',
]

