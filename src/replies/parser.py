import ctypes
import multiprocessing
import re
import time

from bs4 import (
        BeautifulSoup,
        FeatureNotFound,
)
from six.moves.urllib.parse import urlparse

from src import reddit
from src.instagram import Instagram
from src.util import logger


class Parser(object):
    """
    Parses reddit comments for instagram user links
    """

    # XXX: I think creating these here is ok so long as this module is loaded
    # by the main process so that child processes inherit them. otherwise child
    # processes may create another version .. I think.
    _manager = multiprocessing.Manager()
    _cache = _manager.dict()
    # the amount of time before the cache is cleared.
    # too long and the bot may miss any edits to the comment
    # (and the cache may start to impact memory significantly),
    # too short and the number of potential network hits rises.
    _EXPIRE_TIME = 15 * 60
    _expire_timer = multiprocessing.Value(ctypes.c_float, 0.0)

    @staticmethod
    def _prune_cache():
        """
        Clears the cache if the time since the last clearing exceeds the
        threshold
        """
        elapsed = time.time() - Parser._expire_timer.value
        if elapsed > Parser._EXPIRE_TIME:
            logger.id(logger.debug, Parser.__name__, 'Clearing cache ...')
            # XXX: this may cause a comment to be parsed back-to-back if it was
            # just parsed before clear()
            Parser._cache.clear()
            Parser._expire_timer.value = time.time()

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
        Returns a set of valid links in the comment
        """
        # try to clear the cache whenever a comment is parsed
        Parser._prune_cache()

        try:
            links = self.__ig_links

        except AttributeError:
            if not self.comment:
                self.__ig_links = set()

            else:
                try:
                    self.__ig_links = Parser._cache[self.comment.id]

                except KeyError:
                    logger.id(logger.debug, self, 'Parsing comment ...')

                    try:
                        soup = BeautifulSoup(self.comment.body_html, 'lxml')
                    except FeatureNotFound:
                        soup = BeautifulSoup(
                                self.comment.body_html, 'html.parser'
                        )

                    # Note: this only considers valid links in the body's text
                    # TODO? regex search for anything that looks like a link
                    links = set(
                            a['href']
                            for a in soup.find_all('a', href=Instagram.IG_REGEX)
                    )
                    self.__ig_links = links
                    Parser._cache[self.comment.id] = links
                    if links:
                        logger.id(logger.debug, self,
                                'Found #{num} links: {color}',
                                num=len(links),
                                color=links,
                        )

        return links.copy()

    @property
    def ig_usernames(self):
        """
        Returns a set of usernames corresponding to Parser.links
        """
        try:
            usernames = self.__ig_usernames

        except AttributeError:
            usernames = set()
            for link in self.ig_links:
                match = Instagram.IG_REGEX.search(link)
                if match: # this check shouldn't be necessary
                    usernames.add(match.group(2))
            self.__ig_usernames = usernames

        return usernames.copy()


__all__ = [
        'Parser',
]

