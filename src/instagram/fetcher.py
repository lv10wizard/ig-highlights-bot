import time

from .constants import (
        MEDIA_ENDPOINT,
        META_ENDPOINT,
        RATELIMIT_THRESHOLD,
)
from .instagram import Instagram
from src.database import (
        InstagramRateLimitDatabase,
        UniqueConstraintFailed,
)
from src.util import (
        logger,
        requestor,
)
from src.util.decorators import classproperty


class Fetcher(object):
    """
    Instagram requests handling
    """

    _ratelimit = None
    _requestor = None

    # 500-level response status code timing
    # a 500-level status code indicates an error on instagram's side
    _500_timestamp = 0
    _500_delay = 0

    @classproperty
    def ME(cls):
        # 'src.instagram' -> 'instagram'
        return __name__.rsplit('.', 1)[-1]

    @classproperty
    def ratelimit(cls):
        if not Fetcher._ratelimit:
            Fetcher._ratelimit = InstagramRateLimitDatabase(max_age='1h')
        return Fetcher._ratelimit

    @classproperty
    def requestor(cls):
        if not Fetcher._requestor:
            Fetcher._requestor = requestor.Requestor(
                    headers={
                        'User-Agent': Instagram._useragent,
                    },
            )
        return Fetcher._requestor

    @classproperty
    def request_delay_expire(cls):
        return Fetcher._500_timestamp + Fetcher._500_delay

    @staticmethod
    def account_ratelimit(response):
        """
        Account a ratelimit request
        """
        if response is not None:
            try:
                Fetcher.ratelimit.insert(response.url)
            except UniqueConstraintFailed:
                # this shouldn't happen
                logger.id(logger.critical, self,
                        'Failed to count ratelimit hit (#{num} used): {url}',
                        num=Fetcher.ratelimit.num_used(),
                        url=response.url,
                        exc_info=True,
                )
                # TODO? raise
            else:
                Fetcher.ratelimit.commit()

    @staticmethod
    def _handle_rate_limit():
        """
        Checks if the bot has exceeded the instagram ratelimit.

        Returns True if the ratelimit has been exceeded
        """
        try:
            was_ratelimited = Fetcher.__was_ratelimited
        except AttributeError:
            was_ratelimited = False
            Fetcher.__was_ratelimited = was_ratelimited

        num_used = Fetcher.ratelimit.num_used()
        num_remaining = RATELIMIT_THRESHOLD - num_used
        if num_remaining < 0:
            logger.id(logger.warn, Fetcher.ME,
                    'Ratelimit exceeded!'
                    '\n\tused:      {num_used}'
                    '\n\tthreshold: {threshold}'
                    '\n\texcess:    {excess}',
                    num_used=num_used,
                    threshold=RATELIMIT_THRESHOLD,
                    excess=abs(num_remaining),
            )
        is_ratelimited = num_remaining <= 0
        Fetcher.__was_rate_limited = is_ratelimited
        if is_ratelimited and not was_ratelimited:
            time_left = Fetcher.ratelimit.time_left()
            logger.id(logger.info, Fetcher.ME,
                    'Ratelimited! (~ {time} left; expires @ {strftime})',
                    time=time_left,
                    strftime='%H:%M:%S',
                    strf_time=time.time() + time_left,
            )

        elif not is_ratelimited and was_ratelimited:
            logger.id(logger.info, Fetcher.ME,
                    'No longer ratelimited! ({num} requests left)',
                    num=num_remaining,
            )

        return is_ratelimited

    @staticmethod
    def has_server_issue(response):
        return response is not None and response.status_code // 100 == 5

    @staticmethod
    def request(url, *args, **kwargs):
        """
        request call wrapper

        *args, **kwargs are passed to the request call

        Returns the response if the request was made

                or None if the request timed out

                or False if the bot is instagram ratelimited or requests are
                    still delayed due to a 500-level status code
        """
        if (
                # the bot is ratelimited
                Fetcher._handle_rate_limit()
                # or requests are still delayed
                or time.time() < Fetcher.request_delay_expire
        ):
            return False

        response = Fetcher.requestor.request(url, *args, **kwargs)

        # account the ratelimit hit
        Fetcher.account_ratelimit(response)

        if response is not None:
            if Fetcher.has_server_issue(response):
                # instagram is experiencing server issues
                if Fetcher.request_delay_expire <= 0:
                    logger.id(logger.info, Fetcher.ME,
                            '[{status_code}] Server issues detected!',
                            status_code=response.status_code,
                    )

                Fetcher._500_timestamp = time.time()
                Fetcher._500_delay = requestor.choose_delay(
                        Fetcher._500_delay or 1
                )
                logger.id(logger.debug, Fetcher.ME,
                        'Setting delay={time_delay} (expires @ {strftime})',
                        time_delay=Fetcher._500_delay,
                        strftime='%m/%d, %H:%M:%S',
                        strf_time=Fetcher.request_delay_expire,
                )

            elif Fetcher.request_delay_expire > 0:
                # instagram's server issues cleared up
                logger.id(logger.info, Fetcher.ME,
                        '[{status_code}] No longer experiencing server issues',
                        status_code=response.status_code,
                )
                logger.id(logger.debug, Fetcher.ME,
                        'Resetting delay ({time_delay})',
                        time_delay=Fetcher._500_delay,
                )
                Fetcher._500_timestamp = 0
                Fetcher._500_delay = 0

        return response

# ######################################################################

    def __init__(self, user, killed=None):
        self.user = user
        self.killed = killed

    def __str__(self):
        result = [__name__, self.__class__.__name__]
        if self.user:
            result.append(self.user)
        return ':'.join(result)

    def get_meta_data(self):
        """
        Fetches user meta data (eg. num followers, is private, etc)

        Returns a tuple(exists, is_private, num_followers) where
                exists (bool) - whether the user account exists
                is_private (bool) - whether the account is private
                num_followers (int) - the number of followers of the account

                or None if the bot is instagram ratelimited, instagram is
                        experiencing server issues (ie, 500-level status code)
                        or the request timed out
        """
        # TODO: skip if self.user is in ig_queue
        logger.id(logger.info, self, 'Fetching meta data ...')

        response = Fetcher.request(META_ENDPOINT.format(self.user))
        if (
                response is None
                or response is False
                or Fetcher.has_server_issue(response)
        ):
            return

        exists = None
        is_private = None
        num_followers = -1

        if response.status_code == 404:
            # the user does not exist
            exists = False

        else:
            try:
                data = response.json()
            except ValueError:
                # not a valid user (eg. /about page)
                exists = False

            else:
                try:
                    is_private = data['user']['is_private']
                    num_followers = data['user']['followed_by']['count']
                except KeyError:
                    logger.id(logger.exception, self,
                            'Meta data json structure changed!',
                            exc_info=True,
                    )
                    logger.id(logger.debug, self,
                            'json:\n\n{pprint_data}\n\n',
                            pprint_data=data,
                    )
                else:
                    exists = True

        return (exists, is_private, num_followers)

    def fetch_data(self):
        """
        Fetches user data from instagram

        Returns True if all of the user's data was fetched successfully or
                        the account is private
                or None if fetching was interrupted
                or False if the user does not exist or is not a user page
                        eg. instagram.com/about
        """
        pass


__all__ = [
        'Fetcher',
]
