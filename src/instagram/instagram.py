import os

from .constants import BASE_URL
from .cache import Cache
from .fetcher import Fetcher
from constants import EMAIL
from src.util import logger
from src.util.decorators import classproperty
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

    @classproperty
    def request_delay_expire(cls):
        return Fetcher.request_delay_expire

    @classproperty
    def request_delay(cls):
        return Fetcher.request_delay

    @classproperty
    def ratelimit_delay_expire(cls):
        return Fetcher.ratelimit_delay_expire

    @classproperty
    def ratelimit_delay(cls):
        return Fetcher.ratelimit_delay

    @classproperty
    def is_ratelimited(cls):
        return Fetcher.is_ratelimited

    def __init__(self, user, killed=None):
        # all instagram usernames are lowercase
        self.user = user.lower()
        self.cache = Cache(self.user)
        self.fetcher = Fetcher(self.user, killed=killed)

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

    def __getattr__(self, attr):
        try:
            return self.__getattribute__(attr)
        except AttributeError:
            if attr in Fetcher._EXPOSE_PROPS:
                return getattr(self.fetcher, attr)
            else:
                raise

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
    def non_highlighted_media(self):
        """
        Returns a list containing the user's media that the bot does not post
                (effectively, this is set(all_data) - set(top_media))

                See: top_media for documentation on the rest of the possible
                return values.

        Note: this value is cached in memory.
        """
        try:
            media = self.__cached_non_highlighted_media
        except AttributeError:
            media = self._fetch_or_lookup_media(
                    num_highlights=-1,
                    start=Instagram._cfg.num_highlights_per_ig_user,
            )
            self.__cached_non_highlighted_media = media

        return media

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
            media = self._fetch_or_lookup_media()
            # XXX: even the retry/resume value is cached so the expectation
            # is that Instagram instances are not long-lived
            # ie: retry/resume should happen through new instances
            self.__cached_top_media = media

        return media

    def _fetch_or_lookup_media(self, num_highlights=None, start=0):
        """
        Looks up the top media for the user. This method will fetch new data
        if the user's database is expired.

        See top_media for return value documentation.
        """
        if self.fetcher.in_progress:
            # the user is currently being fetched (probably by another process)
            return None

        media = None

        if self.fetcher.should_fetch:
            media = self.fetcher.fetch_data()
            if media:
                # fetch succeeded; reset the media value
                media = None

        if (
                (self.fetcher.valid_response and media is None)
                or self.cache.is_private
        ):
            if self.cache.size() == 0 or not self.private:
                # re-fetch an outdated existing cache
                # (ie: an existing database file no longer reflects the
                #  way the database behaves in code
                #  OR the database is flagged as private but the live account
                #  no longer is)
                # XXX: this logging will be incorrect if the cache is created
                # before this point
                logger.id(logger.debug, self,
                        'Fetching outdated cache ...',
                )
                media = self.fetcher.fetch_data()
                if media:
                    # fetch succeeded; reset the media value
                    media = None

            # check again in case an outdated database fetch failed
            if (
                    # lookup only if all fetches succeeded (if any)
                    (self.fetcher.valid_response and media is None)
                    # or the user account is private
                    or self.cache.is_private
            ):
                media = self._lookup_top_media(num_highlights, start)

        return media

    def _lookup_top_media(self, num_highlights=None, start=0):
        """
        Retreives the top N media for the user from the cache

        num_highlights (int, optional) - the number of highlights to get from
                    the database. -1 will retreive all media sorted by
                    most -> least popular.
                Default: None => get config-defined number
        start (int, optional) - the start index of items to get from the
                    database. Specifying an integer > 0 will effectively
                    skip that number of items.
                Default: 0 => start at the first element
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
            if not num_highlights:
                num_highlights = Instagram._cfg.num_highlights_per_ig_user
            media = self.cache.get_top_media(num=num_highlights, start=start)

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

