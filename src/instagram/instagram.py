import errno
import os
import re
import time

from six import string_types

from .constants import BASE_URL
from constants import EMAIL
from src import database
from src.util import (
        logger,
        requestor,
)
from src.util.version import get_version


def initialize(cfg, bot_username):
    """
    Initializes some cached instagram variables
    """
    if not Instagram._cfg:
        Instagram._cfg = cfg

    if not Instagram._useragent:
        Instagram._useragent = (
                '{username} reddit bot {version} ({email})'.format(
                    username=bot_username,
                    version=get_version(),
                    email=EMAIL,
                )
        )
        logger.id(logger.info, __name__,
                'Using user-agent: \'{user_agent}\'',
                user_agent=Instagram._useragent,
        )

class MissingVariable(Exception): pass

class Instagram(object):
    """
    Instagram object for an individual user.
    This class is not intended to be process safe.
    """

    _cfg = None
    _useragent = None

    def __init__(self, user, killed=None):
        # all instagram usernames are lowercase
        self.user = user.lower()

        if not Instagram._cfg:
            logger.id(logger.critical, self,
                    'I don\'t know where cached instagram is stored:'
                    ' \'_cfg\' not set! Was instagram.initialize(...) called?',
            )
            raise MissingVariable('_cfg')

        if not Instagram._useragent:
            logger.id(logger.critical, self,
                    'I cannot fetch data from instagram: no user-agent set!'
                    ' Was instagram.initialize(...) called?',
            )
            raise MissingVariable('_useragent')

    def __str__(self):
        result = [self.__class__.__name__]
        if self.user:
            result.append(self.user)
        return ':'.join(result)


__all__ = [
        'Instagram',
]

