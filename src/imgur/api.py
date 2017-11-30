from .constants import (
        ALBUM_URL,
        IMAGE_URL,
)
from .uploader import Uploader
from src.util import logger


def get_album(album_hash):
    """
    Gets album information

    album_hash (str) - the album hash to get information of

    Returns the json response containing the album's information
                See: https://api.imgur.com/models/album
            or None if the album does not exist or could not be retreived
    """

    logger.id(logger.info, Uploader.ME,
            'Getting album \'{album_hash}\' ...',
            album_hash=album_hash,
    )

    response = Uploader.request(ALBUM_URL + '/' + album_hash)
    try:
        return response.json()
    except ValueError:
        logger.id(logger.warn, Uploader.ME,
                'Failed to get album \'{album_hash}\': bad json',
                album_hash=album_hash,
                exc_info=True,
        )
    return None

# ######################################################################

def create_album(
        deletehashes=[], title=None, description=None, privacy='hidden',
        cover=None,
):
    """
    Creates an album

    deletehashes (list, optional) - the image deletehashes that should be
                included in the album
    title (str, optional) - the title of the image
    description (str, optional) - the description of the image
    privacy (str, optional) - the privacy level of the album. values are
                'public', 'hidden', 'secret'. if None is specified, the value
                will default to the logged in user's privacy setting
                    Default: 'hidden'
    cover (str, optional) - the image id to use as the cover of the album

    Returns <<TODO>>

    """
    pass

# ######################################################################

def update_album(
        album_hash, deletehashes=[], title=None, description=None,
        privacy='hidden', cover=None,
):
    """
    """
    pass

# ######################################################################

def set_album_images(album_hash, deletehashes=[]):
    """
    """
    pass

# ######################################################################

def add_album_images(album_hash, deletehashes=[]):
    """
    """
    pass

# ######################################################################

def upload_image(
        image, album_hash=None, type_=None, name=None, title=None,
        description=None,
):
    """
    Uploads an image to imgur

    image (file, str) - either the binary file, base64 data, or url to upload
    album (str, optional) - the deletehash of the album that the image should
                be added to
    type_ (str, optional) - the type of the file being uploaded
                either 'file', 'base64', or 'URL'
    name (str, optional) - the name of the file (detected automatically by
                imgur)
    title (str, optional) - the title of the image
    description (str, optional) - the description of the image

    Returns <<TODO>
    """
    pass

# ######################################################################

def update_image(image_hash, title=None, description=None):
    """
    Updates the title and/or description of an image

    image_hash (str) - the image deletehash to update
    title (str, optional) - the title of the image
    description (str, optional) - the description of the image

    Returns <<TODO>
    """
    pass

