import errno
import os
import re
import time

from six import string_types

from constants import EMAIL
from src import database
from src.util import (
        logger,
        requestor,
)
from src.util.version import get_version


# https://stackoverflow.com/a/33783840
# GET json: https://instagram.com/{user}/media
#   {
#       'status': 'ok',
#       'items': [
#           {
#               'alt_media_url': None,
#               'can_delete_comments': False,
#               'can_view_comments': True,
#               'caption': { ... },
#               'code': 'BYtcWH_j31M',
#               'comments': {
#                   'count': 6969,
#                   'data': [ ... ],
#               },
#               'created_time': '1504723393',
#               'id': '1598058108499754316_3224256723',
#               'images': { ... },
#               'likes': {
#                   'count': 2539,
#                   'data': [ ... ],
#               },
#               'link': 'https://www.instagram.com/p/BYtcWH_j31M',
#               'location': '...',
#               'type': 'image',
#               'user': {
#                   'full_name': '...',
#                   'id': '...',
#                   'profile_picture': '...',
#                   'username': '...',
#               },
#           },
#           ...
#           (n = 20)
#       ],
#   }

class MissingVariable(Exception): pass

class Instagram(object):
    """
    Instagram object for an individual user. Fetches data either from instagram
    proper or from cache.

    99% sure this class is NOT process safe.
    """

    cfg = None
    user_agent = None
    _rate_limit = None
    # the max number of requests that can be made before rate-limiting is
    # imposed (this is a rolling limit per max_age, eg. 3000 / hr)
    # XXX: I don't think this should be a config option since the user shouldn't
    # be allowed to change this to any number they wish
    RATE_LIMIT_THRESHOLD = 1000

    _ig_queue = None
    _requestor = None
    _server_error_timestamp = 0
    _server_error_delay = 0

    _BASE_URLS = [
            'instagram.com',
            'instagr.am',

            # random web interface(s) to instagram
            'instaliga.com',
            'picbear.com',
            'vibbi.com',
            'yotagram.com',
            'yooying.com',
    ]
    BASE_URL = _BASE_URLS[0]

    # https://stackoverflow.com/a/33783840
    MEDIA_ENDPOINT = 'https://www.{0}/{{0}}/media'.format(BASE_URL)
    META_ENDPOINT = 'https://www.{0}/{{0}}/?__a=1'.format(BASE_URL)

    # https://stackoverflow.com/a/17087528
    # "30 symbols ... only letters, numbers, periods, and underscores"
    # not sure if information is outdated
    # XXX: periods cannot appear consecutively
    # eg. 'foo.b.a.r' is ok; 'foo..bar' is not
    # XXX: periods cannot appear as the first character nor the last character
    _USERNAME_PTN = r'\w(?!.*[.]{2,})[\w\.]{,29}(?<![.])'
    #                  |\___________/\_________/\______/
    #                  |      |           |         \
    #                  |      |           |    don't match if ends with '.'
    #                  |      |      match 0-29 letters, numbers, underscores
    #                  |    do not match if there are any consecutive periods
    #               first character must be a letter, number or underscore

    _BASE_URL_PTN = r'https?://(?:www[.])?(?:{0})'.format('|'.join(_BASE_URLS))
    #                 \_______/\_________/\_____/
    #                     |         |        \
    #                     |         |     match domain variants
    #                     |     optionally match leading 'www.'
    #                   match scheme 'http://' or 'https://'

    _MEDIA_PATH_PTN = r'p'
    _MEDIA_CODE_PTN = r'[\w\-]{2,}'
    IG_LINK_REGEX = re.compile(
            r'({0})/({1})(?!/{2}/?)(?:/[?].+)?'.format(
            # \___/|\___/\________/\_________/
            #   |  |  |      |           \
            #   |  |  |      |      optionally match trailing queries
            #   |  |  |    don't match if this is a media code
            #   |  |  \
            #   |  |  capture username
            #   | match path separator '/'
            # capture base url

                _BASE_URL_PTN,
                _USERNAME_PTN,
                _MEDIA_CODE_PTN,
            ),
            flags=re.IGNORECASE,
    )

    IG_LINK_QUERY_REGEX = re.compile(
            r'({0})/{1}/{2}/[?].*?taken-by=({3}).*$'.format(
            # \___/ \_/ \_/  | \__________________/
            #   |    |   |   |           \
            #   |    |   |   |  match query string & capture taken-by username
            #   |    |   |  match '?'
            #   |    |  match media code eg. 'BL7JX3LgxQ'
            #   |  match media code path
            # capture base url
                _BASE_URL_PTN,
                _MEDIA_PATH_PTN,
                _MEDIA_CODE_PTN,
                _USERNAME_PTN,
            ),
    )

    IG_USER_REGEX = re.compile(
            r'(?:^|\s+|[(\[])@({0})(?:[)\]]|\s+|$)'.format(
            # \_____________/|\___/\_____________/
            #       |        |  |        \
            #       |        |  |    match whitespace or end of string
            #       |        |  |    or a set of acceptable ending delimiters
            #       |        | capture username
            #       |      only match if username is preceded by '@'
            #       |      -- basically limit guesses at username matches
            #     match start of string or whitespace or a set of acceptable
            #     starting characters
                _USERNAME_PTN,
            ),
            flags=re.IGNORECASE,
    )

    _INSTAGRAM_KEYWORD = r'(?:insta(?:gram)?|ig)'
    #                         \____________/  \
    #                               |       match 'ig'
    #                           match 'insta' or 'instagram'

    # _IG_KEYWORD*: strings that are likely to indicate that the inner substring
    # contains an instagram username.
    _IG_KEYWORD_PREFIX = [
            # match eg. '(IG): ', 'isnta ', etc
            r'\(?{0}\)?:?\s*'.format(_INSTAGRAM_KEYWORD),
            #    \_/    \\_/
            #     |     / |
            #     |     \ optionally match any spaces
            #     |   optionally match ':'
            #    match instagram keywords

            # match eg. 'I think this is their instagram ...'
            #       or  'Her instagram name: ...'
            r'(?:\w+\s+)*{0}(?:\s+\w+)*?:?\s+'.format(
            # \_________/\_/\__________/ \  \
            #      |      |      |       / match trailing spaces
            #      |      |      |   optionally match ':'
            #      |      |   match any extra words
            #      |    match instagram keywords
            #   match any leading words
                _INSTAGRAM_KEYWORD,
            ),
    ]
    _IG_KEYWORD_PREFIX = '|'.join(_IG_KEYWORD_PREFIX)

    _IG_KEYWORD_SUFFIX = r'\s+(?:on\s+{0}|\({0}\))[!.]?'.format(
    #                         \_________/ \______/\___/
    #                              |         |      \
    #                              |         |  optionally match '!' or '.'
    #                              |     match eg. '(IG)'
    #                         match ' on instagram'
            _INSTAGRAM_KEYWORD,
    )

    HAS_IG_KEYWORD_REGEX = re.compile(
            '(?!.*[?])(?:^{0})|(?:{1}$)'.format(
                _IG_KEYWORD_PREFIX,
                _IG_KEYWORD_SUFFIX,
            ),
            flags=re.IGNORECASE,
    )

    IG_USER_STRING_REGEX = [
            # match a prefixed potential instagram username
            # eg. 'IG: foobar'
            r'^(?:{1})@?(?P<prefix>{0})$'.format(
            # |\_____/\_______________/ \
            # |   |           |       only match if at the end of string
            # |   |        capture possible username string
            # \ match instagram keywords prefix
            # only match if at the beginning of the string
                _USERNAME_PTN, _IG_KEYWORD_PREFIX,
            ),

            # match a suffixed potential instagram username
            # eg. 'this is foobar on insta'
            r'(?:^|\s+)@?(?P<suffix>{0})(?:{1})(?:\s+|$)'.format(
            # \_______/\_______________/\_____/\_______/
            #     |            |           |      \
            #     |            |           |   only match if at the end of the
            #     |            |           |     string or followed by spaces
            #     |            |           |
            #     |            |       match instagram keywords suffix
            #     |     capture possible username string
            #   only match if at the beginning of the string or preceded by
            #       spaces
                _USERNAME_PTN, _IG_KEYWORD_SUFFIX
            ),

            # match a possible instagram username if it is the only word
            r'^@?({0})$'.format(_USERNAME_PTN),
            # |\_____/ \
            # |   |  only match entire word
            # \  capture possible username string
            # only match entire word
    ]
    IG_USER_STRING_REGEX = re.compile(
            '|'.join(IG_USER_STRING_REGEX),
            flags=re.IGNORECASE,
    )

    @staticmethod
    def has_server_error():
        """
        Returns whether instagram is experiencing server issues
        """
        return (
                Instagram._server_error_timestamp != 0
                and Instagram._server_error_delay != 0
        )

    @staticmethod
    def is_rate_limited():
        """
        Returns whether we have hit/exceeded the rate-limit
        """
        try:
            was_rate_limited = Instagram.__was_rate_limited
        except AttributeError:
            was_rate_limited = False
            Instagram.__was_rate_limited = was_rate_limited

        num_remaining = Instagram.rate_limit_num_remaining()
        currently_rate_limited = num_remaining <= 0
        Instagram.__was_rate_limited = currently_rate_limited
        if currently_rate_limited and not was_rate_limited:
            time_left = Instagram.rate_limit_time_left()
            logger.id(logger.info, Instagram.__name__,
                    'Ratelimited! (~ {time} left; expires @ {strftime})',
                    time=time_left,
                    strftime='%H:%M:%S',
                    strf_time=time.time() + time_left,
            )

        elif not currently_rate_limited and was_rate_limited:
            logger.id(logger.info, Instagram.__name__,
                    'No longer ratelimited! ({num} requests left)',
                    num=num_remaining,
            )

        return currently_rate_limited

    @staticmethod
    def rate_limit_num_remaining():
        """
        Returns the number requests remaining for the current period
        """
        if Instagram._rate_limit:
            num_used = Instagram._rate_limit.num_used()
            return Instagram.RATE_LIMIT_THRESHOLD - num_used
        return -1

    @staticmethod
    def rate_limit_time_left():
        """
        Returns the time remaining in seconds until new requests can be made
        """
        if Instagram._rate_limit:
            return Instagram._rate_limit.time_left()
        return -1

    @staticmethod
    def initialize(cfg, bot_username):
        """
        Initializes some statically cached instagram variables
        """
        if not Instagram.cfg:
            Instagram.cfg = cfg
        if not Instagram.user_agent:
            Instagram.user_agent = (
                    '{username} reddit bot {version} ({email})'.format(
                        username=bot_username,
                        version=get_version(),
                        email=EMAIL,
                    )
            )
            logger.id(logger.info, __name__,
                    'Using user-agent: \'{user_agent}\'',
                    user_agent=Instagram.user_agent,
            )

        if not Instagram._rate_limit:
            Instagram._rate_limit = database.InstagramRateLimitDatabase(
                    max_age='1h',
            )

    def __init__(self, user, killed=None):
        self.user = user
        self.killed = killed

        if not Instagram.cfg:
            logger.id(logger.critical, self,
                    'I don\'t know where cached instagram data is stored:'
                    ' cfg not set!',
            )
            raise MissingVariable('Please set the Instagram.cfg variable!')

        if not Instagram.user_agent:
            logger.id(logger.critical, self,
                    'I cannot fetch data from instagram: no user-agent!',
            )
            raise MissingVariable(
                    'Please set the Instagram.user_agent variable!'
            )

        if not Instagram._requestor:
            Instagram._requestor = requestor.Requestor(
                    headers={
                        'User-Agent': Instagram.user_agent,
                    },
            )

        if not Instagram._ig_queue:
            Instagram._ig_queue = database.InstagramQueueDatabase()

    def __str__(self):
        result = [self.__class__.__name__]
        if self.user:
            result.append(self.user)
        return ':'.join(result)

    @property
    def __killed(self):
        """
        Returns whether the optional killed flag is set
        """
        was_killed = bool(self.killed)
        if hasattr(self.killed, 'is_set'):
            was_killed = self.killed.is_set()

        if was_killed:
            self.__enqueue()
        return was_killed

    @property
    def url(self):
        return (
                # hard-code the landing page link to sanitize any trailing
                # queries or paths
                'https://www.{0}/{1}'.format(Instagram.BASE_URL, self.user)
                if self.user else None
        )

    @property
    def status_codes(self):
        try:
            return list(self.__status_codes)
        except AttributeError:
            return []

    @property
    def last_id(self):
        try:
            return self.__last_id
        except AttributeError:
            return None

    @property
    def top_media(self):
        """
        Cached wrapper around __get_top_media worker

        This will prevent the same Instagram instance from attempting to fetch
        multiple times if one is necessary.
        """
        try:
            media = self.__cached_top_media
        except AttributeError:
            media = self.__get_top_media()
            self.__cached_top_media = media
        return media

    @property
    def __username_is_ok(self):
        """
        Returns True if there is no cached database for the user or if the
                user's cache is not flagged as bad (private, no-data, or non-
                existant)
        """
        ok = True
        if os.path.exists(self.__db_path):
            try:
                media_cache = self.__cache
            except AttributeError:
                media_cache = database.InstagramDatabase(self.__db_path)
                self.__cache = media_cache

            ok = not media_cache.is_flagged_as_bad

        return ok

    def __get_top_media(self, forced_fetch=False, depth=0):
        """
        Returns the user's most popular media (the exact number is defined in
                the config)
                or None if the fetch was interrupted
                or False if the user's profile is private or not a user page
                    (eg. instagram.com/about)
        """
        if depth > 1:
            # probably about to recurse infinitely.
            # this shouldn't happen.
            raise ValueError('Infinite __get_top_media recursion!')

        data = False
        complete = True
        is_ok = self.__username_is_ok
        if (
                # the cache has expired (or doesn't exist)
                self.__is_expired or (
                    # or the cache is not flagged as bad and either
                    is_ok and (
                        # the fetch was forced
                        forced_fetch
                        # or the last fetch was interrupted
                        or self.user in Instagram._ig_queue
                        # XXX: these two cases should only happen if the cache
                        # was never flagged as bad
                    )
                )
        ):
            complete = self.__fetch_data()
            if not complete:
                # fetch failed; return this value
                data = complete

        elif not is_ok:
            logger.id(logger.debug, self,
                    'Skipping fetch for {color_user}: flagged as bad.',
                    color_user=self.user,
            )

        # don't create a new database file if one does not exist;
        # we should only look up here
        if (
                complete
                and os.path.exists(self.__db_path)
                # XXX: check again if the cache is ok in case the user changed
                # their profile to private
                and self.__username_is_ok
        ):
            num_highlights = Instagram.cfg.num_highlights_per_ig_user
            try:
                media_cache = self.__cache
            except AttributeError:
                media_cache = database.InstagramDatabase(self.__db_path)
            if media_cache.size() == 0:
                # re-fetch an outdated existing cache
                # (outdated meaning the cached version no longer reflects
                #  the way the database behaves in code)
                data = self.__get_top_media(True, depth=depth+1)
            else:
                data = media_cache.get_top_media(num_highlights)
                if num_highlights > 0 and not data:
                    # empty database
                    logger.id(logger.debug, self,
                            'Removing \'{path}\': empty database',
                            path=self.__db_path,
                    )

                    try:
                        os.remove(self.__db_path)

                    except OSError as e:
                        logger.id(logger.warn, self,
                                'Could not remove empty database file'
                                ' \'{path}\'',
                                path=self.__db_path,
                                exc_info=True,
                        )

                elif (
                        hasattr(data, '__iter__')
                        and database.InstagramDatabase.BAD_FLAG in data
                ):
                    # tried to get data for a user that was flagged as bad.
                    # this shouldn't happen
                    logger.id(logger.warn, self,
                            'Attempted to return top-media for a private/'
                            'non-profile/non-existant user!',
                    )
                    data = False

        return data

    @property
    def __db_path(self):
        """
        Returns the user's database file path
        """
        if self.user:
            path = os.path.join(
                    database.InstagramDatabase.PATH,
                    '{0}.db'.format(self.user),
            )
            return database.Database.resolve_path(path)
        return ''

    @property
    def __seen_db_path(self):
        """
        Returns the user's in-progress fetch database file path
        """
        if self.user:
            path = os.path.join(
                    database.InstagramDatabase.PATH,
                    # instagram usernames cannot start with a '.' so this
                    # shouldn't clash with an actual username
                    '.{0}.fetching.db'.format(self.user),
            )
            return database.Database.resolve_path(path)
        return ''

    @property
    def __is_expired(self):
        """
        Returns whether the cache is expired (database age > threshold)
        Returns True if no cached data exists
        """
        expired = False

        try:
            cache_mtime = os.path.getmtime(self.__db_path)

        except OSError as e:
            if e.errno == errno.ENOENT:
                # no cached media
                cache_mtime = 0

            else:
                logger.id(logger.critical, self,
                        'I cannot determine if \'{user}\' media cache is'
                        ' expired! (Could not stat \'{path}\')',
                        user=user,
                        path=self.__db_path,
                        exc_info=True,
                )
                raise

        cache_age = time.time() - cache_mtime
        expired = cache_age > self.cfg.instagram_cache_expire_time
        if cache_mtime > 0 and expired:
            logger.id(logger.debug, self,
                    'Cache expired ({time_age} > {time_expire})',
                    time_age=cache_age,
                    time_expire=self.cfg.instagram_cache_expire_time,
            )

        return expired

    def __enqueue(self):
        """
        Enqueues the user so their in-progress fetch can be continued later.
        This may happen if instagram is ratelimited, experiencing a service
        outage, or the program was killed during a fetch.
        """
        try:
            self.__status_codes
        except AttributeError:
            # if there are no status codes, then no fetch was issued which means
            # that we should not enqueue the user
            return

        if self.user in Instagram._ig_queue:
            queued_last_id = Instagram._ig_queue.get_last_id_for(self.user)
            if (
                    # don't queue invalid data (last_id queued but no last_id
                    # fetched) -- ie, don't restart the fetching sequence
                    (queued_last_id and not self.last_id)
                    # don't re-queue the same data
                    or queued_last_id == self.last_id
            ):
                return

        did_enqueue = False
        msg = ['Queueing']
        if self.last_id:
            msg.append('@ {last_id}')
        msg.append('...')
        logger.id(logger.debug, self,
                ' '.join(msg),
                last_id=self.last_id,
        )

        try:
            with Instagram._ig_queue:
                # XXX: insert() implictly calls update
                Instagram._ig_queue.insert(self.user, self.last_id)

        except database.UniqueConstraintFailed:
            msg = [
                    'Attempted to enqueue duplicate instagram user'
                    ' \'{color_user}\''
            ]
            if self.last_id:
                msg.append('@ {last_id}')

            logger.id(logger.warn, self,
                    ' '.join(msg),
                    color_user=self.user,
                    last_id=self.last_id,
                    exc_info=True,
            )

        else:
            did_enqueue = True
        return did_enqueue

    def __handle_rate_limit(self):
        is_rate_limited = Instagram.is_rate_limited()
        if is_rate_limited:
            self.__enqueue()
        return is_rate_limited

    def __fetch_data(self):
        """
        Fetches user data from instagram

        Returns True if successfully fetches all of the user's data
                or None if fetching was interrupted
                or False if the user is not valid (404 or a private/non-user page
                    eg. instagram.com/about)
        """
        success = None
        if not self.__handle_rate_limit():
            data = None
            last_id = Instagram._ig_queue.get_last_id_for(self.user)
            fatal_msg = [
                    'Failed to fetch \'{user}\' media!'
                    ' Response structure changed.'.format(user=self.user)
            ]

            msg = ['Fetching data']
            if last_id:
                msg.append('(starting @ {last_id})')
            msg.append('...')
            logger.id(logger.info, self,
                    ' '.join(msg),
                    last_id=last_id,
            )

            self.__status_codes = []

            try:
                while not data or data['more_available']:
                    if self.__handle_rate_limit() or self.__killed:
                        break

                    delayed_time = (
                            Instagram._server_error_timestamp
                            + Instagram._server_error_delay
                    )
                    if time.time() < delayed_time:
                        # still delayed
                        logger.id(logger.debug, self,
                                'Fetch delayed for another {time} ...',
                                time=delayed_time - time.time(),
                        )
                        break

                    response = Instagram._requestor.request(
                            Instagram.MEDIA_ENDPOINT.format(self.user),
                            params={
                                'max_id': last_id,
                            },
                    )
                    if response is None:
                        # TODO? enqueue ?
                        break

                    self.__status_codes.append(response.status_code)
                    # count the network hit against the ratelimit regardless of
                    # status code
                    try:
                        self._rate_limit.insert(response.url)
                    except database.UniqueConstraintFailed:
                        logger.id(logger.critical, self,
                                'Failed to count rate-limit hit (#{num} used):'
                                ' {url}',
                                num=self._rate_limit.num_used(),
                                url=response.url,
                                exc_info=True,
                        )
                        # TODO? raise
                    else:
                        self._rate_limit.commit()

                    if response.status_code == 200:
                        if Instagram.has_server_error():
                            logger.id(logger.debug, self,
                                    'Resetting Instagram delay'
                                    ' (t={timestamp}) ...',
                                    timestamp=time.time(),
                            )
                            Instagram._server_error_timestamp = 0
                            Instagram._server_error_delay = 0

                        try:
                            data = response.json()

                        except ValueError as e:
                            # bad json ...?
                            # try again, it may be a temporary error
                            try:
                                num_tries = self.__bad_json_tries
                            except AttributeError:
                                num_tries = 0
                            self.__bad_json_tries = num_tries + 1

                            if num_tries < 10:
                                delay = 5
                                logger.id(logger.warn, self,
                                        'Bad json! Retrying in {time}'
                                        ' (#{num}) ...',
                                        time=delay,
                                        num=num_tries,
                                        exc_info=True,
                                )

                                if (
                                        logger.is_enabled_for(logger.DEBUG)
                                        and isinstance(e.args[0], string_types)
                                ):
                                    # try to determine some context
                                    # '... line 1 column 69152 (char 69151)'
                                    match = re.search(
                                            r'[(]char (\d+)[)]', e.args[0]
                                    )
                                    if match:
                                        # TODO: dynamically determine context
                                        # amount from error -- probably should
                                        # shift to util/json.py or something
                                        idx = int(match.group(1))
                                        ctx = 100
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
                                # too many retries hitting bad json; maybe the
                                # endpoint changed?
                                fatal_msg.append('(bad endpoint?)')
                                logger.id(logger.critical, self,
                                        ' '.join(fatal_msg),
                                        exc_info=True,
                                )
                                self.__enqueue()
                                raise

                        else:
                            try:
                                del self.__bad_json_tries
                            except AttributeError:
                                pass

                            last_id = self.__parse_data(data)
                            if not last_id:
                                if last_id is False:
                                    # private or non-user page
                                    success = False
                                break

                            if not data['more_available']:
                                # parsed the last set of items
                                success = True

                    elif response.status_code == 404:
                        # probably a typo
                        success = False
                        break

                    # elif response.status_code == 403:
                    #     # ip banned by instagram?
                    #     pass # TODO?

                    elif response.status_code // 100 == 4:
                        # client error
                        # just raise, I guess
                        # TODO? enqueue maybe
                        response.raise_for_status()

                    elif response.status_code // 100 == 5:
                        # server error
                        Instagram._server_error_timestamp = time.time()
                        Instagram._server_error_delay = requestor.choose_delay(
                                Instagram._server_error_delay or 1
                        )
                        logger.id(logger.debug, self,
                                'Setting Instagram delay = {delay}'
                                ' (t={timestamp})',
                                delay=Instagram._server_error_delay,
                                timestamp=Instagram._server_error_timestamp,
                        )

                        self.__enqueue()
                        # no reason in trying any more, need to wait until
                        # instagram comes back up
                        break

            except KeyError as e:
                # json structure changed
                fatal_msg.append('(keys={color})')
                logger.id(logger.critical, self,
                        ' '.join(fatal_msg),
                        color=data.keys(),
                        exc_info=True,
                )
                self.__enqueue()
                raise

            except TypeError as e:
                # probably tried to index None (data == None)
                # I'm not sure if this can happen
                logger.id(logger.critical, self,
                        ' '.join(fatal_msg),
                        exc_info=True,
                )
                self.__enqueue()
                raise

        if success is False:
            try:
                self.__cache.flag_as_bad()

            except AttributeError:
                self.__cache = database.InstagramDatabase(self.__db_path)
                self.__cache.flag_as_bad()

        return success

    def __parse_data(self, data, stop_at_first_duplicate=False):
        """
        Parses out relevant information from the response object.

        Returns last_id (string) - eg. '1571552046892748751_3108326'
                - to be used in fetching the next page of data

                or None if stop_at_first_duplicate == True and there was a
                duplicate seen in the current data set
                Note: stop_at_first_duplicate skips pruning missing (deleted)
                    media. This can cause replies to include non-existent
                    links.

                or False if data['items'] is empty
        """
        last_id = None

        if data['status'].lower() == 'ok' and data['items']:
            last_id = data['items'][-1]['id']
            # store the last_id in case we need to enqueue the request for later
            self.__last_id = last_id

            try:
                self.__cache
            except AttributeError:
                self.__cache = database.InstagramDatabase(self.__db_path)

            try:
                seen = self.__seen
            except AttributeError:
                if not stop_at_first_duplicate:
                    # XXX: this is persistent in case the fetch is interrupted
                    # (eg. killed, ratelimited, server issues, etc)
                    seen = database.InstagramDatabase(self.__seen_db_path)
                else:
                    seen = None
                self.__seen = seen

            with self.__cache:
                for item in data['items']:
                    code = item['code']
                    try:
                        self.__cache.insert(item)

                    except database.UniqueConstraintFailed:
                        with self.__cache:
                            self.__cache.update(item)

                        # Note: stop_at_first_duplicate skips pruning.
                        # assumption: media data is fetched newest -> oldest,
                        # meaning we've already seen everything past the first
                        # duplicate.
                        if stop_at_first_duplicate:
                            logger.id(logger.debug, self,
                                    'Already cached \'{code}\' ({id}).'
                                    ' halting ...',
                                    code=code,
                                    id=item['id'],
                            )
                            return None

                    # cache items that have been seen to prune missing
                    # (probably deleted) entries
                    if seen:
                        try:
                            seen.insert(item)

                        except database.UniqueConstraintFailed:
                            # this shouldn't happen since the seen database
                            # should only exist while a fetch is active
                            # XXX: spammy if this does somehow occur
                            logger.id(logger.debug, self,
                                    'Already seen \'{code}\' ({id})!'
                                    ' Was \'{path}\' not deleted?',
                                    code=code,
                                    id=item['id'],
                                    path=self.__seen_db_path,
                            )

                if seen:
                    seen.commit()

            if not data['more_available']:
                if seen:
                    # prune any rows in the cache db that we did not see
                    all_codes = self.__cache.get_all_codes()
                    seen_codes = seen.get_all_codes()
                    logger.id(logger.debug, self,
                            'cached: #{num_cached} vs. fetched: #{num_seen}',
                            num_cached=len(all_codes),
                            num_seen=len(seen_codes),
                    )

                    missing = all_codes - seen_codes
                    if missing:
                        logger.id(logger.info, self,
                                '#{num} links missing (probably deleted).'
                                ' pruning ...'
                                '\ncodes: {color}',
                                num=len(missing),
                                color=missing,
                        )
                        with self.__cache:
                            self.__cache.delete(missing)

                # fetch is finished: remove the seen database
                self.__remove_cache_if_exists(self.__seen_db_path, seen)
                if self.user in Instagram._ig_queue:
                    # remove the user from the queue
                    with Instagram._ig_queue:
                        Instagram._ig_queue.delete(self.user)

        elif not data['items']:
            logger.id(logger.info, self, 'No data. halting ...')
            logger.id(logger.debug, self,
                    '\n\tstatus = \'{status}\'\titems = {items}\n',
                    status=data['status'],
                    items=data['items'],
            )
            # user's profile may be private or may be a non-user page
            last_id = False

        return last_id

    def __remove_cache_if_exists(self, path, cache):
        """
        Removes the database file located at path if it exists
        """
        removed = False
        if os.path.exists(path):
            try:
                cache.close()
            except AttributeError:
                pass

            logger.id(logger.debug, self,
                    'Removing \'{path}\' ...',
                    path=path,
            )

            try:
                os.remove(path)

            except (IOError, OSError):
                logger.id(logger.warn, self,
                        'Could not remove \'{path}\'!',
                        path=path,
                        exc_info=True,
                )

            else:
                removed = True

        return removed


__all__ = [
        'Instagram',
]

