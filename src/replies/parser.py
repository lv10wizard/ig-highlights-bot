import abc
import ctypes
from errno import (
        ECONNABORTED,
        EPIPE,
)
import itertools
import multiprocessing
import re
import time

from bs4 import (
        BeautifulSoup,
        FeatureNotFound,
)
import enchant
from praw.models import (
        Comment,
        Submission,
)
from six import add_metaclass
from six.moves.urllib.parse import urlparse

from src import reddit
from src.config import parse_time
from src.database import (
        BadUsernamesDatabase,
        SubredditsDatabase,
)
from src import instagram
from src.util import (
        logger,
        remove_duplicates,
)


def load_jargon():
    import os

    from constants import (
            JARGON_DEFAULTS_PATH,
            POKEMON_PATH,
    )
    from src.util import (
            format_repeat_each_character_pattern,
            readline,
    )

    jargon = []

    logger.id(logger.debug, __name__,
            'Loading jargon from \'{path}\' ...',
            path=JARGON_DEFAULTS_PATH,
    )
    for i, line in readline(JARGON_DEFAULTS_PATH):
        if line.endswith(','):
            logger.id(logger.warn, __name__,
                    'line #{i} ends with \',\'!',
                    i=i+1,
            )
        jargon.append(line)

    logger.id(logger.debug, __name__,
            'Loading pokemon from \'{path}\' ...',
            path=POKEMON_PATH,
    )
    for i, line in readline(POKEMON_PATH):
        pokemon = map(
                format_repeat_each_character_pattern,
                line.lower()
        )
        jargon.append(''.join(pokemon))

    return jargon

@add_metaclass(abc.ABCMeta)
class _ParserStrategy(object):
    """
    Parsing strategy abstract class
    """

    _subreddits = SubredditsDatabase(do_seed=False)
    _bad_usernames = BadUsernamesDatabase()

    @staticmethod
    def sanitize_link(link):
        """
        Sanitizes the link url
        """
        # parse the url to strip any fragments
        parsed_url = urlparse(link)
        url = []
        if parsed_url.scheme:
            url.append('{0}://'.format(parsed_url.scheme))
        url.append(parsed_url.netloc)
        url.append(parsed_url.path)
        if parsed_url.query:
            url.append('?{0}'.format(parsed_url.query))
        return ''.join(url)

    def __init__(self, thing):
        self.thing = thing
        self._thing_logged = False
        # track whether the usernames were parsed from links or guesses
        # XXX: this assumes that usernames are exclusively parsed from links
        # and other ('@username', suffix, prefix, guesses). that is, if a
        # single username was from a link, this assumes that all were from
        # links. similarly, if one username was a guess then all usernames
        # were guesses.
        self.from_link = None
        self.is_guess = None

    def __str__(self):
        return ':'.join([
            self.__class__.__name__,
            reddit.display_id(self.thing)
        ])

    def _log_thing_text(self):
        if not self._thing_logged:
            logger.id(logger.debug, self,
                    'Text:'
                    '\n\'{text}\'\n',
                    text=self._thing_text,
            )
            self._thing_logged = True

    def _parse_links(self):
        """ Strategy-specific link parsing """
        return self._parse_links_from_html() + self._parse_links_from_text()

    @abc.abstractproperty
    def _thing_text(self):
        """ Returns the thing's text (comment.body or submission.title) """

    @abc.abstractproperty
    def _thing_html(self):
        """
        Returns the thing's text as html
        (comment.body_html or submission.selftext_html)
        """

    def _link_matches(self, link):
        """
        Returns True if the link should be added to the list of parsed links
        """
        result = False
        url = _ParserStrategy.sanitize_link(link)

        logger.id(logger.debug, self,
                'Testing link:'
                '\nactual:    \'{actual}\''
                '\nsanitized: \'{sanitized}\'',
                actual=link,
                sanitized=url,
        )

        match = instagram.IG_LINK_REGEX.search(url)
        if match:
            logger.id(logger.debug, self,
                    'Matched user profile link: {color_link}',
                    color_link=url,
            )
            result = True

        else:
            # try looking for the username in the query in case
            # it is a media link
            match = instagram.IG_LINK_QUERY_REGEX.search(url)
            if match:
                logger.id(logger.debug, self,
                        'Matched query user profile link:'
                        ' {color_link}',
                        color_link=url,
                )
                result = True

        return result

    def _parse_links_from_html(self):
        """
        Parses links from the thing's html

        Returns a list of parsed urls
        """
        links = []
        try:
            soup = BeautifulSoup(self._thing_html, 'lxml')
        except FeatureNotFound:
            soup = BeautifulSoup(self._thing_html, 'html.parser')

        # Note: this only considers valid links in the body's text
        # TODO? regex search for anything that looks like a link
        for a in soup.find_all('a', href=True):
            if self._link_matches(a['href']):
                links.append(a['href'])

        return links

    def _parse_links_from_text(self):
        """
        Parses links from the thing's text

        Returns a list of parsed urls
        """
        self._log_thing_text()
        logger.id(logger.debug, self, 'Testing for links in text ...')

        links = [
                match[0] for match in
                instagram.IG_LINK_REGEX.findall(self._thing_text)
        ]
        if links:
            logger.id(logger.debug, self,
                    'Matched user profile link{plural}: {color_links}',
                    plural=('' if len(links) == 1 else 's'),
                    color_links=links,
            )

        else:
            links = [
                    match[0] for match in
                    instagram.IG_LINK_QUERY_REGEX.findall(self._thing_text)
            ]
            if links:
                logger.id(logger.debug, self,
                        'Matched query user profile link{plural}:'
                        ' {color_links}',
                        plural=('' if len(links) == 1 else 's'),
                        color_links=links,
                )

        return links

    def parse_links(self):
        """
        Returns a list of links found in thing
        """
        fullname = reddit.fullname(self.thing)
        logger.id(logger.debug, self,
                'Parsing {thing} ...',
                thing=reddit.get_type_from_fullname(fullname),
        )

        links = remove_duplicates(self._parse_links())
        if links:
            logger.id(logger.info, self,
                    'Found #{num} link{plural}: {color}',
                    num=len(links),
                    plural=('' if len(links) == 1 else 's'),
                    color=links,
            )

        return links

    def parse_usernames(self):
        """
        Returns a list of unique usernames corresponding to parse_links
        """
        self.from_link = True
        usernames = []
        # look for usernames from links first since they are all but
        # guaranteed to be accurate
        for link in self.parse_links():
            match = instagram.IG_LINK_REGEX.search(link)
            if match:
                usernames.append(match.group('user'))

            else:
                match = instagram.IG_LINK_QUERY_REGEX.search(link)
                if match:
                    usernames.append(match.group('user'))

        if not usernames:
            self.from_link = False
            # try looking username-like strings in the thing in
            # case the user soft-linked one or more usernames
            # eg. '@angiegoesboom'

            # XXX: this will increase the frequency of 404s from general
            # bad matches and may cause the bot to link incorrect user
            # data if someone soft-links eg. a twitter user and a
            # different person owns the same username on instagram.
            self._log_thing_text()
            logger.id(logger.debug, self, 'Testing for users in text ...')

            # try '@username'
            usernames = instagram.IG_AT_USER_REGEX.findall(self._thing_text)
            # TODO: this should not be turned on if the bot is
            # crawling any popular subreddit -- but how to determine
            # if a subreddit is popular?
            # XXX: turn off trying random-ish strings as usernames
            # if the bot is crawling /r/all or if we failed to load
            # the JARGON file
            if (
                    not usernames
                    and Parser._JARGON_FROM_FILE
                    and 'all' not in _ParserStrategy._subreddits
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

            if not self.from_link:
                # prune previous bad matches (eg. usernames that were
                # deleted due to downvotes)
                usernames_db = _ParserStrategy._bad_usernames
                patterns = usernames_db.get_bad_username_patterns()
                bad_username_regex = re.compile(
                        '^(?:{0})$'.format('|'.join(patterns)),
                        flags=re.IGNORECASE,
                )

                pruned = []
                for name in usernames:
                    if bad_username_regex.search(name):
                        usernames.remove(name)
                        pruned.append(name)

                if pruned:
                    logger.id(logger.info, self,
                            'Pruned #{num} previous bad match{plural}:'
                            ' {color_pruned}',
                            num=len(pruned),
                            plural=('' if len(pruned) == 1 else 'es'),
                            color_pruned=pruned,
                    )
                if not usernames:
                    logger.id(logger.info, self, 'All usernames pruned!')

        # force all usernames to lowercase since instagram does not
        # differentiate between cap/low-case
        usernames = [name.lower() for name in usernames]

        return usernames.copy()

    def _get_potential_user_strings(self):
        """
        Tries to find strings in the thing body that could be usernames.

        Returns a list of username candidates
        """
        usernames = []
        body_split = self._thing_text.split('\n')
        # try looking for a non-dictionary, non-jargon word.
        # XXX: matching a false positive will typically result in a
        # private/no-data instagram user if not a 404. relying on the instagram
        # user not having any data to prevent a reply is unwise.
        matches = []
        for text in body_split:
            if (
                    # single word (potentially quoted) in thing
                    len(text.strip('> ').split()) == 1
                    # thing looks like it could contain an instagram user
                    or instagram.HAS_IG_KEYWORD_REGEX.search(text.strip())
            ):
                # XXX: .search() will only match one user per line
                match = instagram.IG_USER_STRING_REGEX.search(text.strip())
                if match:
                    if match.group('guess'):
                        self.is_guess = True
                    matches += list(filter(None, match.groups()))

        for name in matches:
            if not name:
                continue

            # only include strings that could be usernames
            do_add = False
            reason = '???'
            # not too short
            if len(name) <= 5:
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

class _CommentParser(_ParserStrategy):
    """
    Comment parsing strategy
    """
    @property
    def _thing_text(self):
        return self.thing.body

    @property
    def _thing_html(self):
        return self.thing.body_html

class _SubmissionParser(_ParserStrategy):
    """
    Submission parsing strategy
    """
    @property
    def _thing_text(self):
        # treat the title as part of the self-post (assuming the submission is
        # a self-post)
        result = [self.thing.title]
        if self.thing.selftext:
            result.append(self.thing.selftext)
        return '\n'.join(result)

    @property
    def _thing_html(self):
        # non- self-posts' .selftext returns None
        return self.thing.selftext_html or ''

    def _parse_links(self):
        links = _ParserStrategy._parse_links(self)
        # check the post's url in case it links to an instagram profile
        if self._link_matches(self.thing.url):
            links.append(self.thing.url)

        return links

class Parser(object):
    """
    Parses reddit things for instagram user links
    """

    _en_US = None # 'murican
    _en_GB = None # british
    # XXX: internet acronyms evolve rapidly. this regex is not and will never
    # be comprehensive.
    _LAUGH_VOWELS = 'aeou'
    _LAUGH_CONSONANTS = 'hjkwxz'
    _JARGON_VARIATIONS = [
            # https://stackoverflow.com/a/16453542
            # 'lol', 'lllool', 'lololol', etc
            r'(?:(?:l+[{0}]+)+[l{0}]+z*)+\b'.format(_LAUGH_VOWELS),
            #      /  \____/ |\_____/ \
            #      \    |    |   | optionally match trailing 'z's
            #      \    |    | match any number of trailing 'l's
            #      /    |  repeat 'lo', 'llooooo', etc
            #      \  match 'lol', 'lul', 'lel', lal'
            #  match any number of leading 'l's

            'r+o+t*f+l+', # 'rofl', 'rotfl', 'rooofl', etc
            '(?:a+y+)?l+m+f*a+o+h*', # 'lmao', 'lmfao', 'lmaooooo', etc
    ]
    _JARGON_FROM_FILE = load_jargon()
    _JARGON_VARIATIONS_WHOLE = [
            # https://stackoverflow.com/a/16453542
            # 'haha', 'bahaha', 'jajaja', 'kekeke', etc
            '\w?[{0}]*(?:[{1}]+[{0}]+r*)+[{1}]?'.format(
            #\_______/\_________________/   \
            #    |             |         optionally match ending consonant
            #    |    match any number of 'ha', 'haa', 'haaa', etc
            # optionally match leading 'ba', 'baa', 'faaa', etc

                _LAUGH_VOWELS,
                _LAUGH_CONSONANTS,
            ),
    ] + _JARGON_FROM_FILE

    for i, regex in enumerate(_JARGON_VARIATIONS_WHOLE):
        _JARGON_VARIATIONS.append(r'^{0}\b'.format(regex))

    _JARGON_REGEX = re.compile(
            '{0}'.format('|'.join(_JARGON_VARIATIONS)), flags=re.IGNORECASE
    )
    # no longer need to keep the data from file in memory (but keep whether
    # anything was loaded)
    _JARGON_FROM_FILE = bool(_JARGON_FROM_FILE)
    _JARGON_VARIATIONS = bool(_JARGON_VARIATIONS)
    _JARGON_VARIATIONS_WHOLE = bool(_JARGON_VARIATIONS_WHOLE)

    @staticmethod
    def is_english(word):
        """
        Returns True if the word is an english word
        """
        if not Parser._en_US:
            Parser._en_US = enchant.Dict('en_US')
        if not Parser._en_GB:
            Parser._en_GB = enchant.Dict('en_GB')

        return (
                Parser._en_US.check(word)
                or Parser._en_US.check(word.capitalize())
                or Parser._en_GB.check(word)
                or Parser._en_GB.check(word.capitalize())
        )

    @staticmethod
    def is_jargon(word):
        """
        Returns True if the word looks like internet jargon
        """
        return Parser._JARGON_REGEX.search(word)

    def __init__(self, thing):
        self.thing = thing
        if isinstance(thing, Comment):
            self._strategy = _CommentParser(thing)
        elif isinstance(thing, Submission):
            self._strategy = _SubmissionParser(thing)
        else:
            self._strategy = None
            logger.id(logger.warn, self,
                    'Unhandled thing: {color_thing}',
                    color_thing=thing.__repr__(),
            )

    def __str__(self):
        result = [self.__class__.__name__, reddit.display_id(self.thing)]
        if not self._strategy:
            result.append('<invalid>')
        return ':'.join(result)

    @property
    def ig_links(self):
        """
        Returns a list of unique instagram links in the thing
        """
        try:
            links = self.__ig_links

        except AttributeError:
            if not self._strategy:
                links = []
            else:
                links = self._strategy.parse_links()

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
            if not self._strategy:
                usernames = []
            else:
                usernames = self._strategy.parse_usernames()
            self.__ig_usernames = usernames

        return usernames.copy()

    @property
    def from_link(self):
        """
        Returns True if the parsed usernames correspond to hard-linked usernames
        """
        return self._strategy.from_link if self._strategy else None

    @property
    def is_guess(self):
        """
        Returns True if the parsed usernames correspond to guesses
                (single word string that looks like a username)
        """
        return self._strategy.is_guess if self._strategy else None


__all__ = [
        'Parser',
]

