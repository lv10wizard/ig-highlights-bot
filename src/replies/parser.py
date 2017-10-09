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
from six.moves.urllib.parse import urlparse

from src import reddit
from src.config import parse_time
from src.instagram import Instagram
from src.util import (
        logger,
        remove_duplicates,
)


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

                        usernames = [
                                name for name in
                                Instagram.IG_USER_REGEX.findall(
                                    self.comment.body
                                )
                        ]
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


__all__ = [
        'Parser',
]

