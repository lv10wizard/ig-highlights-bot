import errno
import os
import re
import time

from utillib import logger

from src import (
        config,
        database,
)
from util import requestor


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
#               'comments': { ... },
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
    rate_limit_queue = None
    _rate_limit = None
    # the max number of requests that can be made before rate-limiting is
    # imposed (this is a rolling limit per max_age, eg. 3000 / hr)
    # XXX: I don't think this should be a config option since the user shouldn't
    # be allowed to change this to any number they wish
    RATE_LIMIT_THRESHOLD = 3000

    _requestor = None

    BASE_URLS = [
            'instagram.com',
            'instagr.am',

            # random web interface to instagram
            'instaliga.com',
    ]
    BASE_URL = BASE_URLS[0]

    MEDIA_ENDPOINT = 'https://www.{0}/{{0}}/media'.format(BASE_URL)

    # https://stackoverflow.com/a/17087528
    # "30 symbols ... only letters, numbers, periods, and underscores"
    # not sure if information is outdated
    # XXX: periods cannot appear consecutively
    # eg. 'foo.b.a.r' is ok; 'foo..bar' is not
    IG_REGEX = re.compile(
            r'(https?://(?:www[.])?(?:{0})/([\w\.]+)/?)'.format(
            #  \_______/\_________/\_____/|\_______/ \
            #      |         |        |   |    |   optionally match
            #      |         |        |   |    |    trailing '/'
            #      |         |        |   \  capture username
            #      |         |        |  match path separator '/'
            #      |         |  match domain variants
            #      |      optionally match 'www.'
            #    match scheme 'http://' or 'https://'

                '|'.join(BASE_URLS),
            ),
    )

    def __init__(self, user, comment):
        # self.history = database.Database()
        self.user = user
        self.comment = comment

        if not Instagram.cfg:
            logger.prepend_id(logger.debug, self,
                    'I don\'t know where cached instagram data is stored:'
                    ' cfg not set!',
            )
            raise MissingVariable('Please set the Instagram.cfg variable!')

        if not Instagram.rate_limit_queue:
            logger.prepend_id(logger.debug, self,
                    'I can\'t handle enqueing rate-limited data:'
                    ' rate_limit_queue not set!',
            )
            raise MissingVariable(
                    'Please set the Instagram.rate_limit_queue variable!'
            )

        if not Instagram._rate_limit:
            Instagram._rate_limit = database.InstagramRateLimitDatabase(
                    Instagram.cfg.instagram_rate_limit_db_path,
                    max_age=config.parse_time('1h'),
            )

        if not Instagram._requestor:
            Instagram._requestor = requestor.Requestor(
                    headers={
                        'User-Agent': '', # TODO
                    },
            )

    def __str__(self):
        result = filter(None, [
                self.__class__.__name__,
                self.user,
        ])
        return ':'.join(result)

    @property
    def url(self):
        return (
                # hard-code the landing page link to sanitize any trailing
                # queries or paths
                'https://www.{0}/{1}'.format(Instagram.BASE_URL, self.user)
                if self.user else None
        )

    @property
    def valid(self):
        return bool(self.user) and bool(self.top_media)

    @property
    def top_media(self):
        if self.__is_expired:
            self.__fetch_data()

        data = None

        # don't create a new database file if one does not exist;
        # we should only look up here
        if os.path.exists(self.__db_path):
            media_cache = database.InstagramDatabase(self.__db_path)
            num_highlights = Instagram.cfg.num_highlights_per_ig_user
            data = media_cache.get_top_media(num_highlights)
            if num_highlights > 0 and not data:
                # empty database
                try:
                    os.remove(self.__db_path)

                except OSError as e:
                    logger.prepend_id(logger.error, self,
                            'Could not remove empty database file'
                            ' \'{path}\'', e,
                            path=self.__db_path,
                    )

        return data

    @property
    def __db_path(self):
        if self.user:
            return os.path.join(
                    Instagram.cfg.instagram_db_path,
                    '{0}.db'.format(self.user),
            )
        return ''

    @property
    def __is_expired(self):
        """
        Returns whether the cache is expired (database age > threshold)
        Returns True if no cahced data exists
        """
        expired = False

        try:
            cache_mtime = os.path.getmtime(self.__db_path)

        except OSError as e:
            if e.errno == errno.ENOENT:
                # no cached media
                cache_mtime = 0

            else:
                logger.prepend_id(logger.error, self,
                        'I cannot determine if \'{user}\' media cache is'
                        ' expired! (Could not stat \'{path}\')', e, True,
                        user=user,
                        path=self.__db_path,
                )

        cache_age = time.time() - cache_mtime
        expired = cache_age > self.cfg.instagram_cache_expire_time
        if cache_mtime > 0 and expired:
            logger.prepend_id(logger.debug, self,
                    'Cache expired ({time_age} > {time_expire})',
                    time_age=cache_age,
                    time_expire=self.cfg.instagram_cache_expire_time,
            )

        return expired

    @property
    def __is_rate_limited(self):
        """
        Returns whether we have hit/exceeded the rate-limit
        """
        return self.__rate_limit_num_remaining <= 0

    @property
    def __rate_limit_num_remaining(self):
        """
        Returns the number requests remaining for the current period
        """
        return RATE_LIMIT_THRESHOLD - Instagram._rate_limit.num_used()

    @property
    def __rate_limit_reset_time(self):
        """
        Returns the time remaining in seconds until new requests can be made
        """
        return Instagram._rate_limit.time_left()

    def __fetch_data(self):
        """
        Fetches user data from instagram
        """
        if self.__is_rate_limited:
            logger.prepend_id(logger.debug, self,
                    'Rate-limited! (~{time} left)',
                    time=self.__rate_limit_reset_time,
            )
            Instagram.rate_limit_queue.put(self.user, self.comment)

        else:
            data = None
            last_id = None
            fatal_msg = [
                    'Failed to fetch \'{user}\' media!'
                    ' Response structure changed.'.format(user=self.user)
            ]

            logger.prepend_id(logger.debug, self, 'Fetching data ...')

            try:
                while not data or data['more_available']:
                    response = Instagram._requestor.request(
                            Instagram.MEDIA_ENDPOINT.format(self.user),
                            params={
                                'max_id': last_id,
                            },
                    )
                    if response is None:
                        break

                    # count the network hit against the ratelimit regardless of
                    # status code
                    self._rate_limit.insert(response.url)

                    if response.status_code == 200:
                        data = response.json()
                        last_id = self.__parse_data(data)
                        if not last_id:
                            break

                    elif response.status_code == 404:
                        # probably a typo
                        break

                    # elif response.status_code == 403:
                    #     # ip banned by instagram?
                    #     pass # TODO?

                    elif response.status_code / 100 == 4:
                        # client error
                        # just raise, I guess
                        # TODO? enqueue maybe
                        response.raise_for_status()

                    elif response.status_code / 100 == 5:
                        # server error
                        logger.prepend_id(logger.debug, self,
                                'Instagram server error:'
                                ' queueing \'{user}\' fetch ...',
                                user=self.user,
                        )
                        Instagram.rate_limit_queue.put(
                                self.user, self.comment, last_id
                        )

            except KeyError as e:
                # json structure changed
                fatal_msg.append('(keys={unpack_color})')
                logger.prepend_id(logger.error, self,
                        ' '.join(fatal_msg), e, True,
                        unpack_color=data.keys(),
                )

            except TypeError as e:
                # probably tried to index None (data == None)
                # I'm not sure if this can happen
                logger.prepend_id(logger.error, self,
                        ' '.join(fatal_msg), e, True,
                )

            except ValueError as e:
                # response not json (bad endpoint?)
                fatal_msg.append('(bad endpoint?)')
                logger.prepend_id(logger.error, self,
                        ' '.join(fatal_msg), e, True,
                )

    def __parse_data(self, data, stop_at_first_duplicate=False):
        """
        Parses out relevant information from the response object.

        Returns last_id (string) - eg. '1571552046892748751_3108326'
                - to be used in fetching the next page of data

        Returns None if stop_at_first_duplicate == True and there was a
                duplicate seen in the current data set
                Note: stop_at_first_duplicate skips pruning missing (deleted)
                    media. This can cause replies to include non-existent
                    links.
                None is also returned if data['items'] is empty
        """
        last_id = None

        if data['status'].lower() == 'ok' and data['items']:
            last_id = data['items'][-1]['id']

            try:
                cache = self.__cache

            except AttributeError:
                cache = database.InstagramDatabase(self.__db_path)
                self.__cache = cache

            try:
                seen = self.__seen

            except AttributeError:
                seen = set()
                self.__seen = seen

            for item in data['items']:
                try:
                    with self.__cache:
                        self.__cache.insert(item)

                except database.UniqueConstraintFailed:
                    # Note: stop_at_first_duplicate skips pruning
                    # assumption: media data is fetched newest -> oldest
                    if stop_at_first_duplicate:
                        logger.prepend_id(logger.debug, self,
                                'Already cached \'{code}\' ({id}). halting ...',
                                code=code,
                                id=item['id'],
                        )
                        return None

                # cache which codes have been seen so that we can prune missing
                # (probably deleted) entries
                seen.add(code)

            if not data['more_available']:
                # prune any rows in the cache db that we did not see
                missing = self.__cache.get_all_codes() - seen
                if missing:
                    logger.prepend_id(logger.debug, self,
                            '#{num} links missing (probably deleted).'
                            ' pruning ...'
                            '\ncodes: {unpack_color}',
                            num=len(missing),
                            unpack_color=missing,
                    )
                    with self.__cache:
                        self.__cache.delete(missing)

        else:
            logger.prepend_id(logger.debug, self,
                    'No data. halting ...'
                    '\nstatus = \'{status}\'\titems = {items}',
                    status=data['status'],
                    items=data['items'],
            )

        return last_id


__all__ = [
        'Instagram',
]

