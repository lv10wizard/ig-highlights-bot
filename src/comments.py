import re
from urlparse import urlparse

from bs4 import (
        BeautifulSoup,
        FeatureNotFound,
)
from utillib import logger

from src.instagram import Instagram


def display_id(thing):
    if hasattr(thing, 'subreddit_name_prefixed') and hasattr(thing, 'id'):
        return '/'.join([thing.subreddit_name_prefixed, thing.id])
    else:
        return thing

class Parser(object):
    """
    """

    # https://stackoverflow.com/a/17087528
    # "30 symbols ... only letters, numbers, periods, and underscores"
    # not sure if information is outdated
    IG_REGEX = re.compile(
            r'(https?://(?:www[.])?(?:{0}|{1})/([\w\.]+)/?)'.format(
            #  \_______/\_________/\_________/|\_______/ \
            #      |         |          |     |    |   optionally match
            #      |         |          |     |    |    trailing '/'
            #      |         |          |      \  capture username
            #      |         |          |      match path separator '/'
            #      |         |  match domain variants
            #      |      optionally match 'www.'
            #    match scheme 'http://' or 'https://'

                Instagram.BASE_URL,
                Instagram.BASE_URL_SHORT,
            ),
    )

    def __init__(self, comment):
        self.comment = comment
        self.id = comment.id if hasattr(comment, 'id') else None

    def __str__(self):
        if not self.comment:
            return '<invalid comment>'
        return display_id(self.comment)

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

                self.__ig_links = set([
                        a['href']
                        for a in soup.find_all('a', href=Parser.IG_REGEX)
                ])
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
                match = Parser.IG_REGEX.search(link)
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
        'display_id',
        'Parser',
]

