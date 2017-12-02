from .constants import (
        ALBUM_URL,
        IMAGE_URL,
)
from .uploader import Uploader
from src.util import logger


def _is_success(response):
    """
    Returns True if the response data is success
    """
    success = False
    if hasattr(response, 'status_code') and response.status_code == 200:
        try:
            data = response.json()
        except ValueError:
            logger.id(logger.warn, Uploader.ME,
                    'Response does not contain valid json!',
                    exc_info=True,
            )

        else:
            success = data['success']

    return success

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
    if _is_success(response):
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
    title (str, optional) - the title of the album
    description (str, optional) - the description of the album
    privacy (str, optional) - the privacy level of the album. values are
                'public', 'hidden', 'secret'. if None is specified, the value
                will default to the logged in user's privacy setting
                    Default: 'hidden'
    cover (str, optional) - the image id to use as the cover of the album

    Returns True if the album is created successfully
            or False if the album was not created
            or None if the bot is imgur ratelimited or should otherwise retry
                (eg. 500-level status code)
    """

    msg = ['Creating album']
    if title:
        msg.append('\'{title}\'')
    logger.id(logger.info, Uploader.ME,
            ' '.join(msg),
            title=title,
    )

    response = Uploader.request(
            ALBUM_URL,
            method='post',
            data={
                'deletehashes': deletehashes,
                'title': title,
                'description': description,
                'privacy': privacy,
                'cover': cover,
            },
    )
    return _is_success(response)

# ######################################################################

def update_album(
        album_hash, deletehashes=[], title=None, description=None,
        privacy='hidden', cover=None,
):
    """
    Updates the information of an album

    album_hash (str) - the deletehash of the album to update
    deletehashes (list, optional) - the deletehashes of the images that should
                be included in the album
    title (str, optional) - the title of the album
    description (str, optional) - the description of the album
    privacy (str, optional) - the privacy level of the album. values are
                'public', 'hidden', 'secret'. if None is specified, the value
                will default to the logged in user's privacy setting
                    Default: 'hidden'
    cover (str, optional) - the image id to use as the cover of the album

    Returns True if the album is successfully updated
            or False if the album is not successfully updated
            or None if the bot is imgur ratelimited or should otherwise retry
                (eg. 500-level status code)
    """

    msg = []
    if deletehashes:
        msg.append('#{num} image{plural}')
    if title:
        msg.append('title: \'{title}\'')
    if description:
        msg.append('desc: \'{description}\'')
    if privacy:
        msg.append('privacy: \'{privacy}\'')
    if cover:
        msg.append('cover: \'{cover}\'')
    logger.id(logger.info, Uploader.ME,
            'Updating album \'{album_hash}\'{colon}{msg}',
            album_hash=album_hash,
            colon=(':' if msg else ''),
            ' | '.join(msg),
            num=len(deletehashes),
            plural=('' if len(deletehashes) == 1 else 's'),
            title=title,
            description=description,
            privacy=privacy,
            cover=cover,
    )

    response = Uploader.request(
            ALBUM_URL + '/' + album_hash,
            method='put',
            data={
                'deletehashes': deletehashes,
                'title': title,
                'description': description,
                'privacy': privacy,
                'cover': cover,
            },
    )
    return _is_success(response)

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

