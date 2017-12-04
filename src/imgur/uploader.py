import time

from .constants import CREDITS_URL
from src.config import (
        parse_time,
        resolve_path,
)
from src.database import (
        Database,
        ImgurRateLimitDatabase,
)
from src.util import (
        logger,
        requestor,
)
from src.util.decorators import classproperty


class NotInitialized(Exception): pass

class Uploader(object):
    """
    Imgur api lazy-loaded data container

    * This class is NOT intended to be process-safe
    """

    _cfg = None
    _requestor = None
    _ratelimit = None

    _RATELIMIT_RESET_PATH = resolve_path(
            Database.format_path('imgur-ratelimit', dry_run=False)
    )

    @classproperty
    def ME(cls):
        try:
            return __name__.rsplit('.')[-2]
        except IndexError:
            return __name__.rsplit('.')[-1]

    @classproperty
    def cfg(cls):
        from .imgur import Imgur

        if Imgur._cfg:
            Uploader._cfg = Imgur._cfg
        if not Uploader._cfg:
            raise NotInitialized('imgur cfg')
        return Uploader._cfg

    @classproperty
    def requestor(cls):
        from .imgur import Imgur

        if not Uploader._requestor:
            if Imgur._useragent:
                Uploader._requestor = requestor.Requestor(
                        headers={
                            'User-Agent': Imgur._useragent,
                        },
                )
            else:
                raise NotInitialized('imgur user-agent')
        return Uploader._requestor

    @classproperty
    def ratelimit(cls):
        if not Uploader._ratelimit:
            Uploader._ratelimit = ImgurRateLimitDatabase()
        return Uploader._ratelimit

    @staticmethod
    def is_ratelimited(is_post=False):
        """
        Returns True if the client is imgur ratelimited
        """
        remaining = 69 # arbitrary non-ratelimited value

        if is_post:
            remaining = Uploader.ratelimit.get_post_remaining()
        else:
            # check the per-day ratelimit
            remaining = Uploader.ratelimit.get_client_remaining()
            if remaining > 0:
                # check the per-ip, per-hour ratelimit
                remaining = Uploader.ratelimit.get_user_remaining()

        return remaining <= 0

    @staticmethod
    def ratelimit_time_left(is_post=False):
        """
        Returns the number of seconds until the ratelimit resets
                or 0 if the client is not currently imgur ratelimited
        """
        if is_post:
            time_left = Uploader.ratelimit.get_post_time_left()
        else:
            # check the per-ip, per-hour time left first because it is both
            # shorter and more likely to occur
            time_left = Uploader.ratelimit.get_user_time_left()
            if time_left <= 0:
                # fall back to the per-day time left, if any
                time_left = Uploader.ratelimit.get_client_remaining()

        return time_left

    @staticmethod
    def _account_ratelimit(response):
        """
        Accounts a ratelimit hit
        """
        if response is not None:
            # XXX: assumption: only requests that the server responds to count
            # against the client's ratelimit pool

            # XXX: the X-RateLimit-User* headers do not always return an
            # accurate value if the limit has been reset (this may only apply
            # if request has not been issued in a while)

            # XXX: credits appear to only be deducted if the response was not
            # cached by imgur's servers (ie, credits will not be deducted for
            # duplicated requests that occur within a short timeframe or
            # possibly duplicated requests for resources that haven't changed
            # since the last client request)
            # eg. GET 'foobar' album followed immediately by another
            # GET 'foobar' album will only deduct a single credit

            Uploader.ratelimit.insert(response)

    @staticmethod
    def _handle_ratelimit(*args, **kwargs):
        """
        Returns True if currently imgur ratelimited
        """
        try:
            is_post = kwargs['method'].lower() == 'post'
        except (AttributeError, KeyError):
            is_post = False

        is_ratelimited = Uploader.is_ratelimited(is_post)

        try:
            if is_post:
                was_ratelimited = Uploader.__was_post_ratelimited
            else:
                was_ratelimited = Uploader.__was_ratelimited
        except AttributeError:
            was_ratelimited = False

        if is_post:
            Uploader.__was_post_ratelimited = is_ratelimited
        else:
            Uploader.__was_ratelimited = is_ratelimited

        if is_ratelimited and not was_ratelimited:
            time_left = Uploader.ratelimit_time_left(is_post)
            logger.id(logger.info, Uploader.ME,
                    'Ratelimited! (~ {time} left; expires @ {strftime})',
                    time=time_left,
                    strftime='%m/%d, %H:%M:%S',
                    strf_time=time.time() + time_left,
            )
        elif not is_ratelimited and was_ratelimited:
            logger.id(logger.info, Uploader.ME 'No longer ratelimited!')

        return is_ratelimited

    @staticmethod
    def _log_429(response, *args, **kwargs):
        if response.status_code != 429:
            return

        try:
            is_post = kwargs['method'].lower() == 'post'
        except (AttributeError, KeyError):
            is_post = False

        logger.id(logger.warn, Uploader.ME,
                '429 Too Many Requests: ratelimited!',
        )

        if logger.is_enabled_for(logger.DEBUG):
            msg = ['']
            if is_post:
                msg.append(
                        'POST: {post_remaining} / {post_limit}'
                        ' (count: #{post_count})'
                )
            else:
                msg.append(
                        'CLIENT: {client_remaining} / {client_limit}'
                        ' (count: #{client_count})'
                )
                msg.append(
                        'USER: {user_remaining} / {user_limit}'
                        ' (count: #{user_count})'
                )

            logger.id(logger.debug, Uploader.ratelimit,
                    '\n'.join(msg),
                    post_remaining=Uploader.ratelimit.get_post_remaining(),
                    post_limit=Uploader.ratelimit.get_post_limit(),
                    post_count=Uploader.ratelimit.num_post,

                    client_remaining=Uploader.ratelimit.get_client_remaining(),
                    client_limit=Uploader.ratelimit.get_client_limit(),
                    client_count=Uploader.ratelimit.num_client,

                    user_remaining=Uploader.ratelimit.get_user_remaining(),
                    user_limit=Uploader.ratelimit.get_user_limit(),
                    user_count=Uploader.ratelimit.num_user,
            )

    @staticmethod
    def _handle_429(response, *args, **kwargs):
        if response.status_code != 429:
            return

        Uploader._log_429(response, *args, **kwargs)

        # try to determine an appropriate time to wait
        try:
            is_post = kwargs['method'].lower() == 'post'
        except (AttributeError, KeyError):
            is_post = False

        data = Uploader.request_credits()
        user_remaining = 69 # arbitrary non-ratelimited value
        try:
            user_remaining = data['UserRemaining']
        except KeyError:
            pass

        user_reset = time.time() + parse_time('1h')
        try:
            user_reset = data['UserReset']
        except KeyError:
            pass

        client_remaining = 0
        try:
            client_remaining = data['ClientRemaining']
        except KeyError:
            pass

        # TODO: choose longest delay between user/client & only apply
        # post delay if this response was a POST
        # TODO: write expire time to file & prevent requests

    @classproperty
    def _auth_header(cls):
        header = {}
        client_id = Uploader.cfg.imgur_client_id
        if client_id:
            header['Authorization'] = 'Client-ID {0}'.format(client_id)

        return header

    @staticmethod
    def request_credits():
        """
        Issues a request to imgur's /credits api endpoint

        Returns the data JSON dictionary if the request is successful
                or None if the request failed
        """

        data = None
        # XXX: this request should not ever be ratelimited by imgur ... right?
        response = Uploader.requestor.request(
                CREDITS_URL,
                headers=Uploader._auth_header,
        )
        if response is not None:
            failed_msg = 'Failed to fetch imgur credits status'
            try:
                data = response.json()
            except ValueError:
                logger.id(logger.debug, Uploader.ME,
                        '{failed_msg}: bad json!',
                        failed_msg=failed_msg,
                        exc_info=True,
                )

            else:
                if (
                        response.status_code != 200
                        or data['status'] != 200
                        or not data['success']
                ):
                    logger.id(logger.debug, Uploader.ME,
                            '{failed_msg}: non-success status!',
                            failed_msg=failed_msg,
                    )
                    logger.id(logger.debug, Uploader.ME,
                            'response:\n{pprint}\n',
                            pprint=data,
                    )
                    data = None

                else:
                    data = data['data']

        return data

    @staticmethod
    def request(*args, **kwargs):
        """
        Issues a non-authed request

        Returns the response
                or False if either imgur ratelimited or requests are delayed
                    due to a 500-level status code
        """

        if _handle_ratelimit(*args, **kwargs):
            return False

        try:
            kwargs['headers'].update(Uploader._auth_header)
        except (AttributeError, KeyError):
            kwargs['headers'] = Uploader._auth_header

        response = Uploader.requestor.request(*args, **kwargs)
        Uploader._account_ratelimit(response)
        if response is not None:
            try:
                data = response.json()
            except ValueError:
                data = response.text
            logger.id(logger.debug, Uploader.ME,
                    'response:\n{pprint}\n',
                    pprint=data,
            )

            if response.status_code == 429:
                # there is a bug in either the ratelimit database or how
                # the ratelimit is handled; this should not happen.
                Uploader._handle_429(response, *args, **kwargs)

        return response


__all__ = [
        'Uploader',
]

