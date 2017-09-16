import re
from urlparse import urlparse

from bs4 import (
        BeautifulSoup,
        FeatureNotFound,
)
from utillib import logger

from src import reddit
from src.instagram import Instagram


class Parser(object):
    """
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
                logger.prepend_id(logger.spam2, self, 'Parsing comment ...')

                try:
                    soup = BeautifulSoup(comment.body_html, 'lxml')
                except FeatureNotFound:
                    soup = BeautifulSoup(comment.body_html, 'html.parser')

                self.__ig_links = set(
                        a['href']
                        for a in soup.find_all('a', href=Instagram.IG_REGEX)
                )
                links = self.__ig_links
                if links:
                    logger.prepend_id(logger.debug, self,
                            'Found #{num} links: {unpack_color}',
                            num=len(links),
                            unpack_color=links,
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
                logger.prepend_id(logger.debug, self,
                        'Found #{num} usernames: {unpack_color}',
                        num=len(usernames),
                        unpack_color=usernames,
                )

        return usernames.copy()


__all__ = [
        'Parser',
]

