import os

from .constants import BASE_URL
from .cache import Cache
from .fetcher import Fetcher
from constants import EMAIL
from src.util import logger
from src.util.version import get_version


def initialize(cfg, bot_username):
    """
    Initializes some cached instagram variables
    """
    if not Instagram._cfg:
        Instagram._cfg = cfg

    if not Instagram._useragent:
        Instagram._useragent = (
                '{username} reddit bot {version} ({email})'.format(
                    username=bot_username,
                    version=get_version(),
                    email=EMAIL,
                )
        )
        logger.id(logger.info, __name__,
                'Using user-agent: \'{user_agent}\'',
                user_agent=Instagram._useragent,
        )

class MissingVariable(Exception): pass

class Instagram(object):
    """
    Instagram object for an individual user.
    This class is not intended to be process safe.
    """

    _cfg = None
    _useragent = None

    def __init__(self, user, killed=None):
        # all instagram usernames are lowercase
        self.user = user.lower()
        self.cache = Cache(self.user)
        self.fetcher = Fetcher(self.user)

        if not Instagram._cfg:
            logger.id(logger.critical, self,
                    'I don\'t know where cached instagram is stored:'
                    ' \'_cfg\' not set! Was instagram.initialize(...) called?',
            )
            raise MissingVariable('_cfg')

        if not Instagram._useragent:
            logger.id(logger.critical, self,
                    'I cannot fetch data from instagram: no user-agent set!'
                    ' Was instagram.initialize(...) called?',
            )
            raise MissingVariable('_useragent')

    def __str__(self):
        result = [self.__class__.__name__]
        if self.user:
            result.append(self.user)
        return ':'.join(result)

    @property
    def url(self):
        return 'https://www.{0}/{1}'.format(BASE_URL, self.user)

    @property
    def is_private(self):
        return self.cache.is_private

    @property
    def is_bad(self):
        return self.cache.is_bad

    @property
    def top_media(self):
        """
        Returns a list of the user's most popular media
                or None if the fetch was interrupted/should be retried
                or False if the user's profile does not exist, is not a
                    valid user page (eg. /about), or the user has too few
                    followers
                or True if the user's profile is private

        Note: the return value is cached in memory.
        """
        try:
            media = self.__cached_top_media
        except AttributeError:
            media = None

            if self.fetcher.should_fetch:
                media = self._check_metadata()

                if self.fetcher.valid_response and media is None:
                    # metadata check passed
                    media = self.fetcher.fetch_data()
                    if media:
                        # fetch succeeded; reset the media value
                        media = None

            if self.fetcher.valid_response and media is None:
                if self.cache.size() == 0:
                    # re-fetch an outdated existing cache
                    # (ie: an existing database file no longer reflects the
                    #  way the database behaves in code)
                    logger.id(logger.debug, self,
                            'Fetching outdated cache ...',
                    )
                    media = self.fetcher.fetch_data()
                    if media:
                        # fetch succeeded; reset the media value
                        media = None

                # check again in case an outdated database fetch failed
                if self.fetcher.valid_response and media is None:
                    media = self._lookup_top_media()

            # XXX: even the retry/resume value is cached so the expectation
            # is that Instagram instances are not long-lived
            # ie: retry/resume should happen through new instances
            self.__cached_top_media = media

        return media

    def _check_metadata(self):
        """
        Checks the user's metadata to determine if the bot should fetch
        the user's media data.
        """
        result = None
        metadata = self.fetcher.get_meta_data()
        if metadata:
            exists, private, followers = metadata
            min_followers = Instagram._cfg.min_follower_count

            if not exists or followers < min_followers:
                if not exists:
                    logger.id(logger.info, self,
                            '{color_user} does not exist!',
                            color_user=self.user,
                    )

                elif followers < min_followers:
                    logger.id(logger.info, self,
                            '{color_user} has too few followers:'
                            ' skipping. ({num} < {min_count})',
                            color_user=self.user,
                            num=followers,
                            min_count=min_followers,
                    )
                # the user does not exist or has too few followers
                # TODO? differentiate between 404 & too few followers
                self.cache.flag_as_bad()
                result = False

            elif private:
                # the user's profile is private
                self.cache.flag_as_private()
                result = True

        return result

    def _lookup_top_media(self):
        """
        Retreives the top N media for the user from the cache
        """
        if self.cache.is_private:
            logger.id(logger.debug, self,
                    '{color_user} is flagged as private.',
                    color_user=self.user,
            )
            media = True
        elif self.cache.is_bad:
            logger.id(logger.debug, self,
                    '{color_user} is flagged as bad.',
                    color_user=self.user,
            )
            media = False

        else:
            num_highlights = Instagram._cfg.num_highlights_per_ig_user
            media = self.cache.get_top_media(num_highlights)

            if num_highlights > 0 and not media:
                # empty database
                logger.id(logger.debug, self,
                        'Removing \'{path}\': empty database',
                        path=self.cache.dbpath,
                )
                self.cache.close()
                try:
                    os.remove(self.cache.dbpath)

                except OSError:
                    logger.id(logger.warn, self,
                            'Could not remove empty database file'
                            ' \'{path}\'!',
                            path=self.cache.dbpath,
                            exc_info=True,
                    )
                media = False

            elif hasattr(media, '__iter__'):
                # neither of these should happen
                msg = (
                        'Attempted to return top_media for a {adj}'
                        ' user profile!'
                )

                if self.cache.is_bad:
                    logger.id(logger.warn, self,
                            msg,
                            adj='bad',
                    )
                    media = False
                elif self.cache.is_private:
                    logger.id(logger.warn, self,
                            msg,
                            adj='private',
                    )
                    media = True

        return media


__all__ = [
        'Instagram',
]

