import re
import time

from six import string_types

from .constants import (
        MEDIA_ENDPOINT,
        META_ENDPOINT,
        RATELIMIT_THRESHOLD,
)
from .cache import Cache
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
        from .instagram import Instagram

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

    @classproperty
    def is_ratelimited(cls):
        num_used = Fetcher.ratelimit.num_used()
        num_remaining = RATELIMIT_THRESHOLD - num_used
        return num_remaining <= 0

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
    def _is_bad_response(response):
        return (
                response is None
                or response is False
                or Fetcher.has_server_issue(response)
        )

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

    # ##################################################################

    def __init__(self, user, killed=None):
        self.user = user
        self.killed = killed
        self.cache = Cache(user)
        self.last_id = None
        self._fetch_started = False
        self._valid_response = True

    def __str__(self):
        result = [__name__, self.__class__.__name__]
        if self.user:
            result.append(self.user)
        return ':'.join(result)

    @property
    def valid_response(self):
        """
        Returns True if the last request (if any) returned a valid response
                or False if the last response was not valid and not fatal
                        see: _is_bad_response
        """
        return self._valid_response

    @property
    def _killed(self):
        """
        Returns whether the optional killed flag is set
        """
        was_killed = bool(self.killed)
        if hasattr(self.killed, 'is_set'):
            was_killed = self.killed.is_set()

        if was_killed:
            self._enqueue()
        return was_killed

    def _enqueue(self):
        if self._fetch_started:
            self.cache.enqueue(self.last_id)

    def _handle_bad_json(self, err):
        """
        Handles the case where the media endpoint returns invalid json
        """
        try:
            num_tries = self.__bad_json_tries
        except AttributeError:
            num_tries = 0
        self.__bad_json_tries = num_tries + 1

        if num_tries < 10:
            delay = 5
            logger.id(logger.debug, self,
                    'Bad json! Retrying in {time} (#{num}) ...',
                    time=delay,
                    num=num_tries,
                    exc_info=True,
            )

            if (
                    logger.is_enabled_for(logger.DEBUG)
                    and isinstance(err.args[0], string_types)
            ):
                # try to determine some context
                # ' ... line 1 column 69152 (char 69151)'
                match = re.search(r'[(]char (\d+)[)]', err.args[0])
                if match:
                    # TODO: dynamically determine context amount from error
                    # -- probably should shift to util/json.py or something
                    ctx = 100
                    idx = int(match.group(1))
                    start = max(0, idx - ctx)
                    end = min(idx + ctx, len(response.text))
                    logger.id(logger.debug, self,
                            'Response snippet @ {idx}'
                            ' [{start} : {end}]:'
                            '\n\n{snippet}\n\n',
                            idx=idx,
                            start=start,
                            end=end,
                            snippet=response.text[
                                start:end
                            ],
                    )

            if hasattr(self.killed, 'wait'):
                do_wait = self.killed.wait
            else:
                do_wait = time.sleep
            do_wait(delay)

        else:
            # too many retries hitting bad json; maybe the endpoint changed?
            logger.id(logger.critical, self,
                    'Too many bad json retries! Did the endpoint change?'
                    ' ({endpoint})',
                    endpoint=MEDIA_ENDPOINT,
                    exc_info=True,
            )
            self._enqueue()
            raise

    def _reset_bad_json(self):
        """
        Resets the cached variables used to handle bad json
        """
        try:
            del self.__bad_json_tries
        except AttributeError:
            pass

    def _parse_data(self, data):
        """
        Parses a single iteration of the user's media data

        Returns True if the final set of items was successfully parsed
                or False if the /media endpoint returned no items
                or None if there are still more items to be processed
        """
        success = None
        if data['status'].lower() == 'ok' and data['items']:
            self.last_id = data['items'][-1]['id']

            with self.cache:
                for item in data['items']:
                    self.cache.insert(item)

            if not data['more_available']:
                # just parsed the last set of items
                self.cache.finish()
                success = True

        elif not data['items']:
            logger.id(logger.info, self, 'No data: halting ...')
            logger.id(logger.debug, self,
                    '\n\tstatus = \'{status}\'\titems = {pprint_items}\n',
                    status=data['status'],
                    pprint_items=data['items'],
            )
            success = False

        return success

    @property
    def should_fetch(self):
        """
        Returns True if the user's data should be (re-)fetched
        """
        # either cache is expired or does not exist
        # or data was queued for this user from a previous fetch
        # (ie: a fetch should be resumed)
        # -- queued data should imply expired I think
        return self.cache.expired or self.cache.queued_last_id

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
        if Fetcher._is_bad_response(response):
            self._valid_response = False
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

        Returns True if all of the user's data was fetched successfully
                or None if fetching was interrupted
                or False if the user does not exist or is not a user page
                        eg. instagram.com/about
        """
        success = None
        data = None
        self.last_id = self.cache.queued_last_id

        msg = ['Fetching data']
        if self.last_id:
            msg.append('(starting @ {last_id})')
        msg.append('...')
        logger.id(logger.info, self,
                ' '.join(msg),
                last_id=self.last_id,
        )

        try:
            while not data or data['more_available']:
                if self._killed:
                    break

                response = Fetcher.request(
                        MEDIA_ENDPOINT.format(self.user),
                        params={
                            'max_id': self.last_id,
                        },
                )
                if Fetcher._is_bad_response(response):
                    self._enqueue()
                    break

                # seeing one actual response indicates that the fetch has
                # started in earnest
                self._fetch_started = True

                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError as e:
                        # I'm not sure why this happens
                        self._handle_bad_json(e)

                    else:
                        self._reset_bad_json()
                        success = self._parse_data(data)
                        if success is False:
                            # private/non-user page
                            break

                elif response.status_code == 404:
                    # I'm not sure this can happen
                    success = False
                    break

                elif response.status_code // 100 == 4:
                    # client error
                    self._enqueue()
                    response.raise_for_status()

        except (KeyError, TypeError):
            if data:
                logger.id(logger.debug, self,
                        'data:\n\n{pprint_data}\n\n',
                        pprint_data=data,
                )
            logger.id(logger.critical, self,
                    'Failed to fetch {color_user}\'s media!'
                    ' Response structure changed.',
                    color_user=self.user,
                    exc_info=True,
            )
            self._enqueue()
            raise

        if success is False:
            self.cache.flag_as_bad()
        elif success is None:
            self._valid_response = False

        return success


__all__ = [
        'Fetcher',
]

