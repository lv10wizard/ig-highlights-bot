from constants import EMAIL
from src.util import logger
from src.util.version import get_version


def initialize(cfg, username):
    if not Gfycat._cfg:
        Gfycat._cfg = cfg

    if not Gfycat._useragent:
        Gfycat._useragent = (
                '{username} reddit bot {version} ({email})'.format(
                    username=username,
                    version=get_version(),
                    email=EMAIL,
                )
        )
        logger.id(logger.info, __name__,
                'Using user-agent: \'{user_agent}\'',
                user_agent=Gfycat._useragent,
        )

class Gfycat(object):
    """
    """

    _cfg = None
    _useragent = None


__all__ = [
        'initialize',
        'Gfycat',
]

