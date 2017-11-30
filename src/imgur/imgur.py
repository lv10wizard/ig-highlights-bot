from constants import EMAIL
from src.util import logger
from src.util.version import get_version


def initialize(cfg, username):
    if not Imgur._cfg:
        Imgur._cfg = cfg

    if not Imgur._useragent:
        Imgur._useragent = (
                '{username} reddit bot {version} ({email})'.format(
                    username=username,
                    version=get_version(),
                    email=EMAIL,
                )
        )
        logger.id(logger.info, __name__,
                'Using user-agent: \'{user_agent}\'',
                user_agent=Imgur._useragent,
        )

class Imgur(object):
    """
    """

    _cfg = None
    _useragent = None


