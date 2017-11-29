from six import iteritems

from .constants import ALBUM_FOLDERS_URL
from .token import AccessToken
from src.config import resolve_path
from src.database import Database
from src.util import (
        logger,
        requestor,
)
from src.util.decorators import classproperty


class NotInitialized(Exception): pass

class Albums(object):
    """
    Cache of album meta-data
    """

    def __init__(self):
        self._albums = {}

    def __str__(self):
        return self.__class__.__name__

    def __contains__(self, key):
        return key in self._albums

    def __getitem__(self, key):
        return self._albums[key]['id']

    def is_id(self, album_id):
        is_id = False
        for title, album_data in iteritems(self._albums):
            if album_id == album_data['id']:
                is_id = True
                break

        return is_id

    def cache_data(self):
        """
        Caches the album meta-data contained in data

        Returns the json data
                or None if the request failed for any reason
        """
        data = None

        response = Uploader.request_authed(ALBUM_FOLDERS_URL)
        if hasattr(response, 'status_code') and response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                logger.id(logger.warn, Uploader.ME,
                        'Failed to get album-folders: bad response!',
                        exc_info=True,
                )

            else:
                try:
                    for node in data[0]['nodes']:
                        title = node['title']
                        album_data = {
                                'description': node['description'],
                                'id': node['id'],
                                'published': node['published'],
                                'nsfw': node['nsfw'],
                                'title': title,
                        }
                        # XXX: check if the linkText key exists in case the
                        # /name endpoint request failed
                        if 'linkText' in node:
                            album_data['linkText'] = node['linkText']

                        try:
                            self._albums[title].update(album_data)
                        except (AttributeError, KeyError):
                            self._albums[title] = album_data

                except (IndexError, KeyError, TypeError):
                    logger.id(logger.warn, self,
                            'Data structure changed!',
                            exc_info=True,
                    )
                    logger.id(logger.debug, self,
                            'data:\n{pprint}\n',
                            pprint=data,
                    )

        return data

class Uploader(object):
    """
    Gfycat api lazy-loaded data container

    * This class is essentially a static state container; it is not intended
      to be instantiated
    """

    STATUS_INPROGRESS = '__INPROGRESS__'
    STATUS_COMPLETE = '__COMPLETE__'
    STATUS_FAILED = '__FAILED__'
    STATUS_ERROR = '__ERROR__'
    STATUS_INVALID_PERMISSIONS = '__INVALID_PERMISSIONS__'
    STATUS_NOT_FOUND = '__NOTFOUND__'
    STATUS_INVALID_FILE_FORMAT = '__INVALID_FILE_FORMAT__'
    STATUS_TIMEDOUT = '__TIMEDOUT__'

    _cfg = None
    _requestor = None

    # TODO? make thread-safe

    _RATELIMIT_RESET_PATH = resolve_path(
            Database.format_path('gfycat-ratelimit', dry_run=False)
    )

    @classproperty
    def ME(cls):
        try:
            return __name__.rsplit('.')[-2]
        except IndexError:
            return __name__.rsplit('.')[-1]

    @classproperty
    def _access_token(cls):
        """
        Returns a valid access token if the config contains all of the required
                    gfycat auth strings (client_id, client_secret, username,
                    password)
                or None if an access token could not be obtained
        """
        try:
            token = Uploader.__token
        except AttributeError:
            token = AccessToken()
            Uploader.__token = token
        return token.value

    @classproperty
    def cfg(cls):
        from .gfycat import Gfycat
        if not Uploader._cfg:
            Uploader._cfg = Gfycat._cfg
        if not Uploader._cfg:
            raise NotInitialized('gfycat cfg')
        return Uploader._cfg

    @classproperty
    def requestor(cls):
        from .gfycat import Gfycat

        if not Uploader._requestor:
            if Gfycat._useragent:
                Uploader._requestor = requestor.Requestor(
                        headers={
                            'User-Agent': Gfycat._useragent,
                        },
                )
            else:
                raise NotInitialized('gfycat user-agent')
        return Uploader._requestor

    @classproperty
    def albums(cls):
        """
        A lazy-loaded cache of albums to prevent needless checks against album
        existance.

        Note: if a album is altered (deleted, removed, renamed), then
        this cache will cause the program to attempt invalid requests eg.
        adding gfycats to a non-existant album.

        Returns the cached albums object
        """
        try:
            albums = Uploader.__albums
        except AttributeError:
            albums = Albums()
            Uploader.__albums = albums

        return albums

    @classproperty
    def root_album_id(cls):
        """
        Returns the root album id
        """
        try:
            root_id = Uploader.__root_album_id
        except AttributeError:
            root_id = None
            data = Uploader.albums.cache_data()
            if data:
                try:
                    root_id = data[0]['id']
                except (IndexError, KeyError):
                    logger.id(logger.warn, Uploader.ME,
                            'Failed to get root album id:'
                            ' response structure changed!',
                            exc_info=True,
                    )

                Uploader.__root_album_id = root_id

        return root_id

    @staticmethod
    def request_authed(*args, **kwargs):
        """
        Issues an authed request

        Returns the response if an authorized request was made
                or False if no authorized request was made
        """
        response = False

        access_token = Uploader._access_token
        if access_token:
            headers = {'Authorization': 'Bearer {0}'.format(access_token)}
            try:
                kwargs['headers'].update(headers)
            except (AttributeError, KeyError):
                kwargs['headers'] = headers

            response = Uploader.request(*args, **kwargs)

        return response

    @staticmethod
    def request(*args, **kwargs):
        """
        Issues a non-authed request

        Returns the response
        """
        response = Uploader.requestor.request(*args, **kwargs)
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

