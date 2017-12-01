from .constants import ALBUM_URL
from src.config import resolve_path
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
    """

    _cfg = None
    _requestor = None
    _ratelimit = None

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

    @classproperty
    def is_ratelimited(cls):
        """
        Returns True if the client is imgur ratelimited
        """
        pass

    @classproperty
    def is_post_ratelimited(cls):
        """
        Returns True if the client is imgur ratelimited from making POST
        requests
        """
        pass

    @classproperty
    def ratelimit_time_left(cls):
        """
        Returns the number of seconds until the ratelimit resets
                or 0 if the client is not currently imgur ratelimited
        """
        # TODO: return user reset if user-ratelimited otherwise return
        # client reset
        pass

    @classproperty
    def post_ratelimit_time_left(cls):
        """
        Returns the number of seconds until the post ratelimit resets
                or 0 if the client is not currently imgur ratelimited
        """
        # TODO: return user reset if user-ratelimited otherwise return
        # client reset
        pass

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
    def request(*args, **kwargs):
        """
        Issues a non-authed request

        Returns the response
                or <<TODO ratelimit value, server error value>>
        """

        headers = {
                # XXX: this ensures that all requests non-authed
                'Authorization': 'Client-ID {0}'.format(
                    Uploader.cfg.imgur_client_id
                ),
        }
        try:
            kwargs['headers'].update(headers)
        except (AttributeError, KeyError):
            kwargs['headers'] = headers

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

        return response


__all__ = [
        'Uploader',
]

