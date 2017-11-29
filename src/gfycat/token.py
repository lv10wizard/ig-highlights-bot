import json
import os
import time

from .constants import TOKEN_URL
from src.config import resolve_path
from src.database import Database
from src.util import (
        logger,
        readline,
)


class AccessToken(object):
    """
    Access token handling class
    """

    _ACCESS_TOKEN_PATH = resolve_path(
            Database.format_path('gfycat-access-token', dry_run=False)
    )
    _REFRESH_TOKEN_PATH = resolve_path(
            Database.format_path('gfycat-refresh-token', dry_run=False)
    )

    def __str__(self):
        return self.__class__.__name__

    @property
    def value(self):
        """
        Returns the access token
                or None if the access token could not be fetched
        """
        token = self._get_token_from_file(AccessToken._ACCESS_TOKEN_PATH)
        if not token:
            self._remove_file(AccessToken._ACCESS_TOKEN_PATH)
            token = self._request_token()

        return token

    @property
    def _refresh_token(self):
        """
        Returns the refresh token
                or None if there is no refresh token or if the refresh token
                    is expired
        """
        token = self._get_token_from_file(AccessToken._REFRESH_TOKEN_PATH)
        if not token:
            self._remove_file(AccessToken._REFRESH_TOKEN_PATH)

        return token

    def _request_token(self):
        """
        Requests new access/refresh tokens from gfycat and writes them to their
        respective files

        Returns the access token
                or None if the access token could not be fetched
        """
        from .uploader import Uploader

        token = None

        client_id = client_secret = username = password = None
        if Uploader.cfg:
            client_id = Uploader.cfg.gfycat_client_id
            client_secret = Uploader.cfg.gfycat_client_secret
            username = Uploader.cfg.gfycat_username
            password = Uploader.cfg.gfycat_password

        if client_id and client_secret and username and password:
            request_data = {
                    'client_id': client_id,
                    'client_secret': client_secret,
            }

            refresh_token = self._refresh_token
            if refresh_token:
                request_data.update({
                    'grant_type': 'refresh',
                    'refresh_token': refresh_token,
                })

            else:
                request_data.update({
                    'grant_type': 'password',
                    'username': username,
                    'password': password,
                })

            response = Uploader.request(TOKEN_URL,
                    method='post',
                    data=json.dumps(request_data),
            )

            if response is not None and response.status_code == 200:
                try:
                    data = response.json()
                except ValueError:
                    # TODO? retry request?
                    logger.id(logger.warn, self,
                            'Failed to request gfycat access/refresh tokens!',
                            exc_info=True,
                    )

                else:
                    try:
                        token = data['access_token']
                        access_expires_in = data['expires_in']
                        refresh_token = data['refresh_token']
                        refresh_expires_in = data['refresh_token_expires_in']
                    except KeyError:
                        logger.id(logger.warn, self,
                                'Malformed token data:\n{pprint}\n',
                                pprint=data,
                                exc_info=True,
                        )
                    else:
                        self._write_to_file(
                                AccessToken._ACCESS_TOKEN_PATH,
                                token, access_expires_in,
                        )
                        self._write_to_file(
                                AccessToken._REFRESH_TOKEN_PATH,
                                refresh_token, refresh_expires_in,
                        )

            else:
                logger.id(logger.warn, self,
                        'Could not request gfycat access/refresh tokens!'
                        ' ({status}: {reason})',
                        status=response.status_code,
                        reason=response.reason,
                )

        return token

    def _get_token_from_file(self, path):
        """
        Returns the token contained in the token's file path if it is not
                    expired
                or None if the token is expired, the file is malformed, or
                    the file does not exist
        """
        if not os.path.exists(path):
            return None

        token = None

        expire_timestamp = 0
        for i, line in readline(path):
            if not token:
                token = line
            elif not expire_timestamp:
                expire_timestamp = line

        if token and expire_timestamp:
            try:
                expire_timestamp = float(expire_timestamp)
            except (TypeError, ValueError):
                logger.id(logger.warn, self,
                        'Malformed token file ({path}):'
                        ' invalid expire_timestamp=\'{expire_timestamp}\'',
                        path=path,
                        expire_timestamp=expire_timestamp,
                        exc_info=True,
                )
                token = None
            else:
                time_remaining = expire_timestamp - time.time()
                if time_remaining <= 0:
                    logger.id(logger.debug, self,
                            'Previous token expired {time} ago'
                            ' (@ {strftime})',
                            time=abs(time_remaining),
                            strftime='%m/%d, %H:%M:%S',
                            strf_time=expire_timestamp,
                    )
                    token = None

        elif token:
            # file isn't complete
            logger.id(logger.debug, self,
                    'Token file malformed: \'{path}\'!',
                    path=path,
            )
            token = None

        return token

    def _write_to_file(self, path, token, expires_in):
        """
        Writes the token file

        Returns True if the file is successfully written
        """
        written = False

        try:
            expire_timestamp = time.time() + expires_in
        except TypeError:
            logger.id(logger.warn, self,
                    'Cannot write token file:'
                    ' invalid expires_in timestamp ({expires_in})',
                    expires_in=expires_in,
                    exc_info=True,
            )

        else:
            logger.id(logger.debug, self,
                    'Writing \'{path}\': expires in {time} (@ {strftime})',
                    path=path,
                    time=expires_in,
                    strftime='%m/%d, %H:%M:%S',
                    strf_time=expire_timestamp,
            )

            try:
                with open(path, 'w') as fd:
                    fd.write('\n'.join([str(token), str(expire_timestamp)]))
            except (IOError, OSError):
                logger.id(logger.exception, self,
                        'Failed to write \'{path}\'!',
                        path=path,
                )
            else:
                written = True

        return written

    def _remove_file(self, path):
        """
        Removes the token file path

        Returns True if the file is successfully removed
                or None if the file does not exist
        """
        if not os.path.exists(path):
            return None

        removed = False

        logger.id(logger.debug, self,
                'Removing \'{path}\' ...',
                path=path,
        )

        try:
            os.remove(path)
        except OSError:
            logger.id(logger.exception, self,
                    'Failed to remove \'{path}\'!',
                    path=path,
            )
        else:
            removed = True

        return removed


__all__ = [
        'AccessToken',
]

