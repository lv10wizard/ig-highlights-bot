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

    @classproperty
    def is_ratelimited(cls):
        """
        Returns True if the client is imgur ratelimited
        """
        pass

    @staticmethod
    def _account_ratelimit(response):
        """
        Accounts a ratelimit hit
        """
        if response is not None:
            # XXX: assumption: only requests that the server responds to count
            # against the client's ratelimit pool

            # TODO: account per-ip (X-RateLimit-User{Limit,Remaining,Reset})
            # TODO: account per-client (X-RateLimit-Client{Limit,Remaining})
            # TODO: (in ImgurRateLimitDatabase) always keep 1 credit as buffer
            #   because I don't think imgur sends an accurate count
            pass

    @staticmethod
    def request(*args, **kwargs):
        """
        Issues a non-authed request

        Returns the response
                or <<TODO ratelimit value, server error value>>
        """

        headers = {
                # XXX: this makes all requests non-authed
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

