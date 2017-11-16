import ctypes
import multiprocessing
import os
import re
import time

from six import string_types

from .constants import (
        MEDIA_ENDPOINT, # XXX: broken as of Nov 7, 2017 (always 404s)
        META_ENDPOINT,
        RATELIMIT_THRESHOLD,
)
from .cache import Cache
from src.config import (
        parse_time,
        resolve_path,
)
from src.database import (
        Database,
        InstagramRateLimitDatabase,
        UniqueConstraintFailed,
)
from src.util import (
        logger,
        readline,
        requestor,
)
from src.util.decorators import classproperty


class Fetcher(object):
    """
    Instagram requests handling
    """

    _ratelimit = None
    _requestor = None
    _cfg = None

    # 500-level response status code timing
    # a 500-level status code indicates an error on instagram's side
    _500_timestamp = multiprocessing.Value(ctypes.c_double, 0.0)
    _500_delay = multiprocessing.Value(ctypes.c_double, 0.0)

    # 429-level response status code timing
    _429_timestamp = multiprocessing.Value(ctypes.c_double, 0.0)
    _429_delay = multiprocessing.Value(ctypes.c_double, 0.0)
    _429_DEFAULT_DELAY = parse_time('5m')

    _was_ratelimited = multiprocessing.Value(ctypes.c_bool, False)

    _RATELIMIT_RESET_PATH = resolve_path(
            Database.PATH_FMT.format('instagram_ratelimit')
    )

    _EXPOSE_PROPS = [
            'exists',
            'private',
            'verified',
            'full_name',
            'external_url',
            'biography',
            'num_followers',
            'num_follows',
            'num_posts',
    ]

    @classproperty
    def ME(cls):
        try:
            # 'src.instagram.fetcher' -> 'instagram'
            return __name__.rsplit('.')[-2]
        except IndexError:
            # directory structure changed, probably.
            # this should return 'fetcher' (the name of this file)
            return __name__.rsplit('.')[-1]

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
        return Fetcher._500_timestamp.value + Fetcher._500_delay.value

    @classproperty
    def request_delay(cls):
        """
        Returns the time remaining until requests can be made again due to
                encountering a 500-level status code
        """
        time_left = -1

        expire = Fetcher.request_delay_expire
        if expire > 0:
            time_left = expire - time.time()

        return time_left

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
                logger.id(logger.critical, Fetcher.ME,
                        'Failed to count ratelimit hit (#{num} used): {url}',
                        num=Fetcher.ratelimit.num_used(),
                        url=response.url,
                        exc_info=True,
                )
                # TODO? raise
            else:
                Fetcher.ratelimit.commit()

    @classproperty
    def ratelimit_delay_expire(cls):
        expire = 0

        time_left = Fetcher.ratelimit_delay
        if time_left > 0:
            expire = time.time() + time_left

        return expire

    @classproperty
    def ratelimit_delay(cls):
        time_left = -1

        # try a 429-based ratelimit
        expire = Fetcher._429_timestamp.value + Fetcher._429_delay.value
        if expire > 0:
            time_left = expire - time.time()

        # try the self-imposed ratelimit
        if time_left < 0:
            num_remaining = RATELIMIT_THRESHOLD - Fetcher.ratelimit.num_used()
            if num_remaining <= 0:
                time_left = Fetcher.ratelimit.time_left()

        return time_left

    @classproperty
    def is_ratelimited(cls):
        return Fetcher.ratelimit_delay > 0

    @staticmethod
    def _log_ratelimit():
        time_left = Fetcher.ratelimit_delay
        if time_left > 0:
            logger.id(logger.info, Fetcher.ME,
                    'Ratelimited! (~ {time} left; expires @ {strftime})',
                    time=time_left,
                    strftime='%H:%M:%S',
                    strf_time=time.time() + time_left,
            )

    @staticmethod
    def _handle_rate_limit():
        """
        Checks if the bot has exceeded the instagram ratelimit.

        Returns True if the ratelimit has been exceeded
        """

        was_ratelimited = Fetcher._was_ratelimited.value

        # try loading a previously recorded ratelimit
        Fetcher._load_ratelimit_reset()

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

        is_ratelimited = Fetcher.is_ratelimited
        Fetcher._was_ratelimited.value = is_ratelimited

        if not is_ratelimited:
            Fetcher._remove_recorded_ratelimit()

        if not is_ratelimited and was_ratelimited:

            # TODO: determine why this not always called when the ratelimit
            # state changes from True -> False.

            logger.id(logger.info, Fetcher.ME, 'No longer ratelimited!')
            # just reset the 429 variables even if the ratelimit was
            # self-imposed
            # TODO? call this if not is_ratelimited so that the timing
            # variables always reflect the current state
            Fetcher._reset_ratelimit()

        return is_ratelimited

    @staticmethod
    def _reset_ratelimit():
        Fetcher._429_timestamp.value = Fetcher._429_delay.value = 0
        try:
            del Fetcher._multi_429_count
        except AttributeError:
            pass

    @staticmethod
    def _load_ratelimit_reset():
        """
        Loads the ratelimit reset time from file (this assumes the ratelimit
        is a 429 ratelimit, not a self-imposed ratelimit)

        Returns True if the ratelimit reset time was successfully loaded
        """
        timestamp_set = False
        delay_set = False
        if Fetcher.is_ratelimited:
            if os.path.exists(Fetcher._RATELIMIT_RESET_PATH):
                logger.id(logger.debug, Fetcher.ME,
                        'Loading previous ratelimit from \'{path}\' ...',
                        path=Fetcher._RATELIMIT_RESET_PATH,
                )

                for i, line in readline(Fetcher._RATELIMIT_RESET_PATH):
                    try:
                        if not timestamp_set:
                            Fetcher._429_timestamp.value = float(line)
                            timestamp_set = True
                        elif not delay_set:
                            Fetcher._429_delay.value = float(line)
                            delay_set = True

                    except (TypeError, ValueError):
                        # recorded data structure changed or corrupted
                        logger.id(logger.warn, Fetcher.ME,
                                'Invalid ratelimit reset time:'
                                ' \'{data}\' in \'{path}\'',
                                data=line,
                                path=Fetcher._RATELIMIT_RESET_PATH,
                                exc_info=True,
                        )
                        Fetcher._reset_ratelimit()
                        break

                    else:
                        if timestamp_set and delay_set:
                            logger.id(logger.debug, Fetcher.ME,
                                    'Loaded ratelimit reset from file:'
                                    '\n\ttimestamp: {strftime}'
                                    '\n\tdelay:     {time_delay}',
                                    strftime='%m/%d, %H:%M:%S',
                                    strf_time=Fetcher._429_timestamp.value,
                                    time_delay=Fetcher._429_delay.value,
                            )
                            # break in case there are too many lines in the
                            # file (which could indicate that the file
                            # structure changed but the loading code did not)
                            break

            else:
                Fetcher._remove_recorded_ratelimit()

        return timestamp_set and delay_set

    @staticmethod
    def _record_ratelimit_reset():
        """
        Records the ratelimit reset time to file
        """
        if Fetcher.ratelimit_delay > 0:
            if os.path.exists(Fetcher._RATELIMIT_RESET_PATH):
                logger.id(logger.debug, FETCHER.ME,
                        'Overwriting previous ratelimit time @ \'{path}\'!',
                        path=Fetcher._RATELIMIT_RESET_PATH,
                )
                data = [
                        line for _, line in
                        readline(Fetcher._RATELIMIT_RESET_PATH)
                ]
                if data:
                    logger.id(logger.debug,
                            os.path.basename(Fetcher._RATELIMIT_RESET_PATH),
                            'data:\n{data}\n',
                            data='\n'.join(data),
                    )

            logger.id(logger.debug, Fetcher.ME,
                    'Writing ratelimit time: {strftime} ...',
                    strftime='%H:%M:%S',
                    strf_time=Fetcher.ratelimit_delay_expire,
            )

            try:
                with open(Fetcher._RATELIMIT_RESET_PATH, 'w') as fd:
                    # XXX: write the delay relative to the current time
                    # in case the ratelimit is self-imposed
                    fd.write('{0}\n{1}'.format(
                        time.time(),
                        Fetcher.ratelimit_delay,
                    ))

            except (IOError, OSError):
                logger.id(logger.exception, Fetcher.ME,
                        'Failed to record ratelimit time: {strftime}',
                        strftime='%H:%M:%S',
                        strf_time=Fetcher.ratelimit_delay_expire,
                )

    @staticmethod
    def _remove_recorded_ratelimit():
        if os.path.exists(Fetcher._RATELIMIT_RESET_PATH):
            logger.id(logger.debug, Fetcher.ME,
                    'Removing ratelimit reset time file \'{path}\' ...',
                    path=Fetcher._RATELIMIT_RESET_PATH,
            )

            try:
                os.remove(Fetcher._RATELIMIT_RESET_PATH)

            except (IOError, OSError):
                logger.id(logger.warn, Fetcher.ME,
                        'Failed to remove \'{path}\'!',
                        path=Fetcher._RATELIMIT_RESET_PATH,
                        exc_info=True,
                )

    @staticmethod
    def _handle_too_many_requests(response):
        """
        Handles 429 Too Many Requests response
        """
        if response.status_code == 429:
            logger.id(logger.info, Fetcher.ME,
                    '429 Too Many Requests: ratelimited!',
            )

            if not Fetcher.is_ratelimited:
                if (
                        Fetcher._429_timestamp.value > 0
                        or Fetcher._429_delay.value > 0
                ):
                    # this should not happen. it indicates a bug in how the
                    # ratelimit is reset.
                    logger.id(logger.debug, Fetcher.ME,
                            'Previous 429 timing not reset!'
                            '\ntimestamp:  {strftime}'
                            '\norig delay: {time}',
                            strftime='%m/%d, %H:%M:%S',
                            strf_time=(
                                Fetcher._429_timestamp.value
                                + Fetcher._429_delay.value
                            ),
                            time=Fetcher._429_delay.value,
                    )

                Fetcher._429_timestamp.value = time.time()
                try:
                    Fetcher._429_delay.value = float(
                            # https://tools.ietf.org/html/rfc6585#section-4
                            response.headers['retry-after']
                    # add some extra time because instagram's header seems
                    # to be short
                    ) + 90.0
                    logger.id(logger.debug, Fetcher.ME,
                            'Setting delay from Retry-After header: {time}',
                            time=Fetcher._429_delay.value,
                    )
                except (KeyError, TypeError, ValueError):
                    Fetcher._429_delay.value = Fetcher._429_DEFAULT_DELAY
                    logger.id(logger.debug, Fetcher.ME,
                            'Setting to default delay: {time}',
                            time=Fetcher._429_delay.value,
                    )

                Fetcher._log_ratelimit()
                Fetcher._record_ratelimit_reset()

            else:
                try:
                    Fetcher._multi_429_count += 1
                except AttributeError:
                    Fetcher._multi_429_count = 1

                # made another request past the first 429 response
                # (this will probably be spammy)
                # TODO? raise instead
                logger.id(logger.warn, Fetcher.ME,
                        'Multiple requests made while 429 ratelimited!'
                        ' (#{num})',
                        num=Fetcher._multi_429_count,
                )

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

                Fetcher._500_timestamp.value = time.time()
                Fetcher._500_delay.value = requestor.choose_delay(
                        Fetcher._500_delay.value or 1
                )
                logger.id(logger.debug, Fetcher.ME,
                        'Setting delay={time_delay} (expires @ {strftime})',
                        time_delay=Fetcher._500_delay.value,
                        strftime='%m/%d, %H:%M:%S',
                        strf_time=Fetcher.request_delay_expire,
                )

            if response.status_code == 429: # too many requests
                Fetcher._handle_too_many_requests(response)

            elif Fetcher.request_delay_expire > 0:
                # instagram's server issues cleared up
                logger.id(logger.info, Fetcher.ME,
                        '[{status_code}] No longer experiencing server issues',
                        status_code=response.status_code,
                )
                logger.id(logger.debug, Fetcher.ME,
                        'Resetting delay ({time_delay})',
                        time_delay=Fetcher._500_delay.value,
                )
                Fetcher._500_timestamp.value = 0
                Fetcher._500_delay.value = 0

        return response

    # ##################################################################

    def __init__(self, user, killed=None):
        self.user = user
        self.killed = killed
        self.cache = Cache(user)
        self.last_id = None
        self._fetch_started = False
        self._valid_response = True

        self._exists = None
        self._private = None
        self._verified = None
        self._full_name = None
        self._external_url = None
        self._biography = None
        self._num_followers = None
        self._num_follows = None # num accounts the user follows
        self._num_posts = None

        if not Fetcher._cfg:
            from .instagram import Instagram
            Fetcher._cfg = Instagram._cfg

    def __str__(self):
        result = [Fetcher.ME, self.__class__.__name__]
        if self.user:
            result.append(self.user)
        return ':'.join(result)

    def _get_meta_property(self, attr):
        result = None
        if hasattr(self, attr):
            if getattr(self, attr) is None:
                self._get_meta_data()
            result = getattr(self, attr)
        else:
            # most likely a programmer error (eg. typo)
            logger.id(logger.critical, self,
                    'No such attribute \'{attr}\'!',
                    attr=attr,
            )

        return result

    @property
    def exists(self):
        """ Returns whether the account exists """
        return self._get_meta_property('_exists')

    @property
    def private(self):
        """ Returns whether the account is private """
        return self._get_meta_property('_private')

    @property
    def verified(self):
        """ Returns whether the account is verified """
        return self._get_meta_property('_verified')

    @property
    def full_name(self):
        """ Returns the account's full_name """
        return self._get_meta_property('_full_name')

    @property
    def external_url(self):
        """ Returns the account's external_url """
        return self._get_meta_property('_external_url')

    @property
    def biography(self):
        """ Returns the account's biography """
        return self._get_meta_property('_biography')

    @property
    def num_followers(self):
        """ Returns the account's number of followers """
        return self._get_meta_property('_num_followers') or -1

    @property
    def has_enough_followers(self):
        """
        Returns True if the account has enough followers for a fetch to occur
                or False if the account does not have enough followers
                or None if _num_followers is not set
        """
        if self.num_followers < 0:
            return None
        return self.num_followers >= Fetcher._cfg.min_follower_count

    @property
    def num_follows(self):
        """ Returns the number of users the account follows """
        return self._get_meta_property('_num_follows') or -1

    @property
    def num_posts(self):
        """ Returns the account's number of public posts """
        return self._get_meta_property('_num_posts') or -1

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

    def _wait(self, delay):
        if delay > 0:
            if hasattr(self.killed, 'wait'):
                do_wait = self.killed.wait
            else:
                do_wait = time.sleep

            logger.id(logger.debug, self,
                    'Waiting {time} ...',
                    time=delay,
            )

            do_wait(delay)

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

            self._wait(delay)

        else:
            # too many retries hitting bad json; maybe the endpoint changed?
            logger.id(logger.critical, self,
                    'Too many bad json retries! Did the endpoint change?'
                    ' ({endpoint})',
                    endpoint=META_ENDPOINT,
                    exc_info=True,
            )
            self._enqueue()
            raise

    def _reset_error_delay(self):
        """
        Resets the cached variables used to handle bad json
        """
        try:
            del self.__bad_json_tries
        except AttributeError:
            pass

    def _has_more(self, data):
        return data['user']['media']['page_info']['has_next_page']

    def _parse_data(self, data):
        """
        Parses a single iteration of the user's media data

        Returns True if the final set of items was successfully parsed
                or False if the /media endpoint returned no items
                or None if there are still more items to be processed
        """
        success = None
        nodes = data['user']['media']['nodes']
        if nodes:
            self.last_id = nodes[-1]['id']

            with self.cache:
                for item in nodes:
                    self.cache.insert(item)

            if not self._has_more(data):
                # just parsed the last set of items
                self.cache.finish()
                success = True

        else:
            logger.id(logger.info, self, 'No data: halting ...')
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

    def _parse_meta_data(self, data):
        """
        Parses the user's meta data if it has not yet been parsed for this
        instance
        """

        def parse(data, entire_data, *keys):
            try:
                # lookup the next dictionary key
                result = data[keys[0]]
            except KeyError:
                logger.id(logger.debug, self,
                        'data:\n{pprint_data}',
                        pprint_data=entire_data,
                )
                logger.id(logger.warn, self,
                        'Meta-data json structure changed!'
                        ' No such key=\'{key}\'',
                        key=keys[0],
                        exc_info=True,
                )
                return None

            if not isinstance(result, dict) or len(keys) == 1:
                # either the current key resulted in a non-dictionary
                # or parsed through all of the given keys
                return result
            else:
                # continue parsing the keys
                return parse(result, entire_data, *keys[1:])

        def set_meta_val(attr, data, *keys):
            # only set if the attribute already exists
            if hasattr(self, attr):
                # and if the attribute is None
                # XXX: this is an issue if a valid value for an attribute is
                # None.
                if getattr(self, attr) is None:
                    result = parse(data, data, *keys)
                    logger.id(logger.debug, self,
                            '{attr}: {val}',
                            attr=attr,
                            val=result,
                    )
                    setattr(self, attr, result)

            else:
                # probably a typo
                logger.id(logger.critical, self,
                        'No such attribute \'{attr}\'!',
                        attr=attr,
                )

        set_meta_val('_private', data, 'user', 'is_private')
        set_meta_val('_verified', data, 'user', 'is_verified')
        set_meta_val('_full_name', data, 'user', 'full_name')
        set_meta_val('_external_url', data, 'user', 'external_url')
        # TODO: does an empty biography == None or == ''?
        set_meta_val('_biography', data, 'user', 'biography')
        set_meta_val('_num_followers', data, 'user', 'followed_by', 'count')
        set_meta_val('_num_follows', data, 'user', 'follows', 'count')
        set_meta_val('_num_posts', data, 'user', 'media', 'count')

        if self._private:
            logger.id(logger.info, self,
                    '{color_user} is private!',
                    color_user=self.user,
            )
            self.cache.flag_as_private()

        if self.has_enough_followers is False:
            logger.id(logger.info, self,
                    '{color_user} has too few followers:'
                    ' skipping. ({num} < {min_count})',
                    color_user=self.user,
                    num=self._num_followers,
                    min_count=Fetcher._cfg.min_follower_count,
            )
            # TODO? differentiate between non-existant & too few followers
            self.cache.flag_as_bad()

    def _set_does_not_exist(self):
        self._exists = False
        logger.id(logger.info, self,
                '{color_user} does not exist!',
                color_user=self.user,
        )
        self.cache.flag_as_bad()

    def _get_meta_data(self):
        """
        Fetches & parses user meta data (eg. num followers, is private, etc)
        """
        # TODO: skip if self.user is in ig_queue
        logger.id(logger.info, self, 'Fetching meta data ...')

        data = None
        while not data:
            response = Fetcher.request(META_ENDPOINT.format(self.user))
            if Fetcher._is_bad_response(response):
                # wait out the delay
                request_delay = Fetcher.request_delay
                ratelimit_delay = Fetcher.ratelimit_delay
                delay = max(request_delay, ratelimit_delay)
                if delay <= 0:
                    # non-ratelimit, non-server issue related delay;
                    # just choose a default delay
                    delay = 60

                logger.id(logger.debug, self,
                        'Bad response! Waiting {time} (expires @ {strftime})',
                        time=delay,
                        strftime='%H:%M:%S',
                        strf_time=time.time() + delay,
                )

                self._killed.wait(delay)

            elif response is not None:
                if response.status_code == 200:
                    self._exists = True

                    try:
                        data = response.json()
                    except ValueError as e:
                        # either bad json or a non-user page
                        if response.text.strip().startswith('{'):
                            # most likely bad json
                            self._handle_bad_json(e)
                        else:
                            # most likely a non-user page (eg. /about)
                            break

                elif response.status_code == 404:
                    self._set_does_not_exist()
                    break

                elif response.status_code == 429: # too many requests
                    self._wait(Fetcher.ratelimit_delay)
                    if self._killed:
                        break

                elif response.status_code // 100 == 4:
                    response.raise_for_status()

        self._reset_error_delay()

        if data:
            self._reset_error_delay()
            self._parse_meta_data(data)

    def fetch_data(self):
        """
        Fetches user data from instagram

        Returns True if all of the user's data was fetched successfully
                or None if fetching was interrupted
                or False if the user does not exist or is not a user page
                        eg. instagram.com/about
                        or if the user's account is private
                        or if the user has too few followers
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
            while not data or self._has_more(data):
                if self._killed:
                    break

                response = Fetcher.request(
                        META_ENDPOINT.format(self.user),
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
                    self._exists = True

                    try:
                        data = response.json()
                    except ValueError as e:
                        # I'm not sure why this happens
                        self._handle_bad_json(e)

                    else:
                        self._reset_error_delay()
                        self._parse_meta_data(data)
                        if self.has_enough_followers is False:
                            success = False

                        if success is None:
                            success = self._parse_data(data)

                        # XXX: not an 'elif' in case _parse_data changed the
                        # success value.
                        if success is False:
                            # private/non-user page/not enough followers
                            break

                elif response.status_code == 404:
                    self._set_does_not_exist()
                    success = False
                    break

                elif response.status_code == 429: # too many requests
                    self._enqueue()
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

        if success is None:
            self._valid_response = False

        return success


__all__ = [
        'Fetcher',
]

