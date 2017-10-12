import ctypes
from errno import (
        ECONNABORTED,
        EPIPE,
)
import multiprocessing
import re
import time

from bs4 import (
        BeautifulSoup,
        FeatureNotFound,
)
import enchant
from six.moves.urllib.parse import urlparse

from src import reddit
from src.config import parse_time
from src.database import SubredditsDatabase
from src.instagram import Instagram
from src.util import (
        logger,
        remove_duplicates,
)


def load_jargon():
    import os

    from constants import JARGON_DEFAULTS_PATH

    jargon = []
    logger.id(logger.debug, __name__,
            'Loading jargon from \'{path}\' ...',
            path=JARGON_DEFAULTS_PATH,
    )
    try:
        with open(JARGON_DEFAULTS_PATH, 'r') as fd:
            for i, line in enumerate(fd):
                try:
                    comment_idx = line.index('#')
                except ValueError:
                    # no comment in line
                    comment_idx = len(line)

                # too spammy
                # comment = line[comment_idx:].strip()
                # if comment:
                #     logger.id(logger.debug, __name__,
                #             'Skipping comment: \'{comment}\'',
                #             comment=comment,
                #     )

                regex = line[:comment_idx].strip()
                if regex:
                    # too spammy
                    # logger.id(logger.debug, __name__,
                    #         'Adding jargon: \'{regex}\'',
                    #         regex=regex,
                    # )
                    if regex.endswith(','):
                        logger.id(logger.warn, __name__,
                                'line #{i} ends with \',\'!',
                                i=i+1,
                        )
                    jargon.append(regex)

    except (IOError, OSError):
        logger.id(logger.exception, __name__,
                'Failed to load jargon file: \'{path}\'!',
                path=JARGON_DEFAULTS_PATH,
        )

    return jargon

class _Cache(object):
    """
    Inter-process parsed comment cache
    """

    _manager = multiprocessing.Manager()

    # the amount of time before the cache is cleared.
    # too long and the bot may miss any edits to the comment
    # (and the cache may start to impact memory significantly),
    # too short and the number of potential network hits rises.
    EXPIRE_TIME = parse_time('15m')

    NON_FATAL_ERR = [ECONNABORTED, EPIPE]

    def __init__(self, name=None):
        self.name = name
        self._expire_timer = multiprocessing.Value(ctypes.c_float, 0.0)
        self.cache = _Cache._manager.dict()

    def __str__(self):
        result = [__name__, self.__class__.__name__]
        if self.name:
            result.append(self.name)
        return ':'.join(result)

    def __setitem__(self, key, item):
        try:
            self.cache[key] = item
        except (BrokenPipeError, ConnectionAbortedError) as e:
            if e.errno in _Cache.NON_FATAL_ERR:
                # Software caused connection abort
                # (shutdown interrupted lookup)
                pass
            else:
                raise

    def __getitem__(self, key):
        self._clear()
        try:
            item = self.cache[key]
        except (BrokenPipeError, ConnectionAbortedError) as e:
            if e.errno in _Cache.NON_FATAL_ERR:
                # Software caused connection abort
                # (shutdown interrupted lookup)
                item = []
            else:
                raise
        except KeyError:
            item = None
        return item

    def _clear(self):
        """
        Clears the cache if the time since it was last cleared exceeds the
        threshold
        """
        elapsed = time.time() - self._expire_timer.value
        if elapsed > _Cache.EXPIRE_TIME:
            logger.id(logger.debug, self,
                    'Clearing cache (#{num}) ...',
                    num=len(self.cache),
            )
            # XXX: this may cause a comment to be parsed back-to-back if it was
            # parsed just before clear()
            try:
                self.cache.clear()
            except (BrokenPipeError, ConnectionAbortedError) as e:
                if e.errno in _Cache.NON_FATAL_ERR:
                    pass
                else:
                    raise
            self._expire_timer.value = time.time()

class Parser(object):
    """
    Parses reddit comments for instagram user links
    """

    # list of authors whose comments should not be parsed for soft-links
    # XXX: these should be in lower-case
    IGNORE = [
            'automoderator',
    ]

    # XXX: I think creating these here is ok so long as this module is loaded
    # by the main process so that child processes inherit them. otherwise child
    # processes may create another version .. I think.
    _link_cache = _Cache('links')
    _username_cache = _Cache('usernames')

    _subreddits = SubredditsDatabase(do_seed=False)

    _en_US = None # 'murican
    _en_GB = None # british
    # XXX: internet acronyms evolve rapidly. this regex is not and will never
    # be comprehensive.
    _LAUGH_VOWELS = 'aeou'
    _LAUGH_CONSONANTS = 'hjkxz'
    _JARGON_VARIATIONS = [
            # https://stackoverflow.com/a/16453542
            '(?:l+[ouea]+)+l+z*', # 'lol', 'lllool', 'lololol', etc
            #   / \_____/ | \ \
            #   \    |    |  \ optionally match trailing 'z's
            #   \    |    | match any number of trailing 'l's
            #   /    |  repeat 'lo', 'llooooo', etc
            #   \  match 'lol', 'lul', 'lel', lal'
            #  match any number of leading 'l's

            'r+o+t*f+l+', # 'rofl', 'rotfl', 'rooofl', etc
            'l+m+f*a+o+', # 'lmao', 'lmfao', 'lmaooooo', etc
    ]
    _JARGON_FROM_FILE = load_jargon()
    _JARGON_VARIATIONS_WHOLE = [
            # https://stackoverflow.com/a/16453542
            # 'haha', 'bahaha', 'jajaja', 'kekeke', etc
            '\w?[{0}]*(?:[{1}][{0}]+r*)+[{1}]?'.format(
            #\_______/\________________/   \
            #    |             |       optionally match ending consonant
            #    |    match any number of 'ha', 'haa', 'haaa', etc
            # optionally match leading 'ba', 'baa', 'faaa', etc

                _LAUGH_VOWELS,
                _LAUGH_CONSONANTS,
            ),
    ] + _JARGON_FROM_FILE

    for i, regex in enumerate(_JARGON_VARIATIONS_WHOLE):
        _JARGON_VARIATIONS.append(r'\b{0}\b'.format(regex))

    _JARGON_REGEX = re.compile(
            '^{0}$'.format('|'.join(_JARGON_VARIATIONS)), flags=re.IGNORECASE
    )

    @staticmethod
    def is_english(word):
        """
        Returns True if the word is an english word
        """
        if not Parser._en_US:
            Parser._en_US = enchant.Dict('en_US')
        if not Parser._en_GB:
            Parser._en_GB = enchant.Dict('en_GB')

        return Parser._en_US.check(word) or Parser._en_GB.check(word)

    @staticmethod
    def is_jargon(word):
        """
        Returns True if the word looks like internet jargon
        """
        return Parser._JARGON_REGEX.search(word)

    def __init__(self, comment):
        self.comment = comment

    def __str__(self):
        result = [self.__class__.__name__]
        if not self.comment:
            result.append('<invalid comment>')
        else:
            result.append(reddit.display_id(self.comment))
        return ':'.join(result)

    @property
    def ig_links(self):
        """
        Returns a list of unique instagram links in the comment
        """
        try:
            links = self.__ig_links

        except AttributeError:
            if not self.comment:
                links = []

            else:
                links = Parser._link_cache[self.comment.id]
                if links is None:
                    logger.id(logger.debug, self, 'Parsing comment ...')

                    try:
                        soup = BeautifulSoup(self.comment.body_html, 'lxml')
                    except FeatureNotFound:
                        soup = BeautifulSoup(
                                self.comment.body_html, 'html.parser'
                        )

                    # Note: this only considers valid links in the body's text
                    # TODO? regex search for anything that looks like a link
                    links = []
                    for a in soup.find_all('a', href=True):
                        # parse the url to strip any queries or fragments
                        parsed_url = urlparse(a['href'])
                        url = '{0}://{1}{2}'.format(
                                parsed_url.scheme,
                                parsed_url.netloc,
                                parsed_url.path,
                        )
                        match = Instagram.IG_LINK_REGEX.search(url)
                        if match:
                            links.append(url)

                    links = remove_duplicates(links)
                    # cache the links in case a new Parser is instantiated for
                    # the same comment, potentially from a different process
                    Parser._link_cache[self.comment.id] = links
                    if links:
                        logger.id(logger.info, self,
                                'Found #{num} link{plural}: {color}',
                                num=len(links),
                                plural=('' if len(links) == 1 else 's'),
                                color=links,
                        )
            # cache a reference to the links on the instance in case the
            # object is long-lived
            self.__ig_links = links

        return links.copy()

    @property
    def ig_usernames(self):
        """
        Returns a list of unique usernames corresponding to Parser.links
        """
        try:
            usernames = self.__ig_usernames

        except AttributeError:
            usernames = []
            if self.comment:
                # look for usernames from links first since they are all but
                # guaranteed to be accurate
                for link in self.ig_links:
                    match = Instagram.IG_LINK_REGEX.search(link)
                    if match: # this check shouldn't be necessary
                        usernames.append(match.group(2))

                author = self.comment.author
                author = author and author.name.lower()

                if not usernames and author not in Parser.IGNORE:
                    # try looking username-like strings in the comment body in
                    # case the user soft-linked one or more usernames
                    # eg. '@angiegoesboom'

                    # XXX: this will increase the frequency of 404s from general
                    # bad matches and may cause the bot to link incorrect user
                    # data if someone soft-links eg. a twitter user and a
                    # different person owns the same username on instagram.
                    usernames = Parser._username_cache[self.comment.id]
                    if usernames is None:
                        logger.id(logger.debug, self,
                                '\nLooking for soft-linked users in body:'
                                ' \'{body}\'\n',
                                body=self.comment.body,
                        )

                        # try '@username'
                        usernames = Instagram.IG_USER_REGEX.findall(
                                self.comment.body
                        )
                        # TODO: this should not be turned on if the bot is
                        # crawling any popular subreddit -- but how to determine
                        # if a subreddit is popular?
                        # XXX: turn off trying random-ish strings as usernames
                        # if the bot is crawling /r/all or if we failed to load
                        # the JARGON file
                        if (
                                not usernames
                                and Parser._JARGON_FROM_FILE
                                and 'all' not in Parser._subreddits
                        ):
                            # try looking for possible username strings
                            usernames = self._get_potential_user_strings()

                        usernames = remove_duplicates(usernames)
                        if usernames:
                            logger.id(logger.info, self,
                                    'Found #{num} username{plural}: {color}',
                                    num=len(usernames),
                                    plural=('' if len(usernames) == 1 else 's'),
                                    color=usernames,
                            )

            Parser._username_cache[self.comment.id] = usernames
            self.__ig_usernames = usernames

        return usernames.copy()

    def _get_potential_user_strings(self):
        """
        Tries to find strings in the comment body that could be usernames.

        Returns a list of username candidates
        """
        LENGTH_THRESHOLD = 4
        usernames = []
        # try looking for a non-dictionary, non-jargon word.
        # XXX: matching a false positive will typically result in a
        # private/no-data instagram user if not a 404. relying on the instagram
        # user not having any data to prevent a reply is unwise.
        body = self.comment.body.strip()
        if (
                # single word comment
                len(body.split()) == 1
                # comment looks like it could contain an instagram user
                or Instagram.HAS_IG_KEYWORD_REGEX.search(body)
        ):
            matches = Instagram.IG_USER_STRING_REGEX.findall(body)
            for name in matches:
                # only include strings that could be usernames
                do_add = False
                reason = '???'
                # not too short
                if len(name) <= 4:
                    reason = 'too short ({0})'.format(len(name))
                else:
                    # not some kind of internet jagon
                    match = Parser.is_jargon(name)
                    if match:
                        reason = 'is jargon: \'{0}\''.format(match.group(0))
                    # not an english word
                    elif Parser.is_english(name):
                        reason = 'is english: \'{0}\''.format(name)

                    else:
                        do_add = True

                if do_add:
                    usernames.append(name)

                else:
                    logger.id(logger.debug, self,
                            'Potential username, {color_name}, failed:'
                            ' {reason}',
                            color_name=name,
                            reason=reason,
                    )

        return usernames


__all__ = [
        'Parser',
]

