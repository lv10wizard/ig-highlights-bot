import re

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

    def __init__(self, comment):
        self.comment = comment

    def __str__(self):
        if not self.comment:
            return '<invalid comment>'
        return reddit.display_id(self.comment)

    @property
    def ig_links(self):
        """
        Returns a set of valid links in the comment
        """
        try:
            links = self.__ig_links

        except AttributeError:
            if not self.comment:
                self.__ig_links = set()

            else:
                logger.id(logger.debug, self, 'Parsing comment ...')

                try:
                    soup = BeautifulSoup(self.comment.body_html, 'lxml')
                except FeatureNotFound:
                    soup = BeautifulSoup(self.comment.body_html, 'html.parser')

                # Note: this only considers valid links in the body's text
                # TODO? regex search for anything that looks like a link
                self.__ig_links = set(
                        a['href']
                        for a in soup.find_all('a', href=Instagram.IG_REGEX)
                )
                links = self.__ig_links
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
            self.__ig_usernames = set()
            for link in self.ig_links:
                match = Instagram.IG_REGEX.search(link)
                if match: # this check shouldn't be necessary
                    self.__ig_usernames.add(match.group(2))
            usernames = self.__ig_usernames
            if usernames:
                logger.id(logger.debug, self,
                        'Found #{num} usernames: {color}',
                        num=len(usernames),
                        color=usernames,
                )

        return usernames.copy()


__all__ = [
        'Parser',
]

