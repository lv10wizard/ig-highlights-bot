import os

from .constants import (
        ALBUM_URL,
        IMAGE_URL,
)
from .uploader import Uploader
from src.config import resolve_path
from src.util import logger


def _is_success(response):
    """
    Returns True if the response data is success
            or None if the response data does not indicate success
            or False if the bot is imgur ratelimited or should otherwise retry
                (eg. 500-level status code)
    """
    success = None
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
            if not success:
                # XXX: return None instead of False to match the Uploader's
                # .request ratelimited return value
                success = None

    # TODO: check for server-level (500) errors
    elif response is False or Uploader.is_ratelimited:
        success = False

    return success

def _prepare_deletehashes(deletehashes):
    return ','.join(deletehashes) if deletehashes else None

# ######################################################################

def get_album(album_hash):
    """
    Gets album information

    album_hash (str) - the album hash to get information of

    Returns the json response containing the album's information
                See: https://api.imgur.com/models/album
            or None if the album does not exist or could not be retreived
            or False if the bot is imgur ratelimited or should otherwise retry
                (eg. 500-level status code)
    """

    logger.id(logger.info, Uploader.ME,
            'Getting album \'{album_hash}\' ...',
            album_hash=album_hash,
    )

    response = Uploader.request(ALBUM_URL + '/' + album_hash)
    success = _is_success(response)
    if success:
        try:
            return response.json()
        except ValueError:
            logger.id(logger.warn, Uploader.ME,
                    'Failed to get album \'{album_hash}\': bad json',
                    album_hash=album_hash,
                    exc_info=True,
            )
    return success

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
            or None if the album was not created
            or False if the bot is imgur ratelimited or should otherwise retry
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
                'deletehashes': _prepare_deletehashes(deletehashes),
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
            or None if the album is not successfully updated
            or False if the bot is imgur ratelimited or should otherwise retry
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
            colon=(':\n' if msg else ''),
            msg='\n'.join(msg),
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
                'deletehashes': _prepare_deletehashes(deletehashes),
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
    Sets the images for an album, removing all other images

    album_hash (str) - the deletehash of the album to set the images for
    deletehashes (list, optional) - the deletehashes of the images to set the
                album to

    Returns True if the album images are successfully set
            or None if the album images are not successfully set
            or False if the bot is imgur ratelimited or should otherwise retry
                (eg. 500-level status code)
    """

    logger.id(logger.info, Uploader.ME,
            'Setting album \'{album_hash}\' images: #{num} image{plural}',
            album_hash=album_hash,
            num=len(deletehashes),
            plural=('' if len(deletehashes) == 1 else 's'),
    )

    response = Uploader.request(
            ALBUM_URL + '/' + album_hash,
            method='post',
            data={
                'deletehashes': _prepare_deletehashes(deletehashes),
            },
    )
    return _is_success(response)

# ######################################################################

def add_album_images(album_hash, deletehashes=[]):
    """
    Adds the images to an album

    album_hash (str) - the deletehash of the album to set the images for
    deletehashes (list, optional) - the deletehashes of the images to set the
                album to

    Returns True if the album images are successfully set
            or None if the album images are not successfully set
            or False if the bot is imgur ratelimited or should otherwise retry
                (eg. 500-level status code)
    """

    logger.id(logger.info, Uploader.ME,
            'Adding album \'{album_hash}\' images: #{num} image{plural}',
            album_hash=album_hash,
            num=len(deletehashes),
            plural=('' if len(deletehashes) == 1 else 's'),
    )

    response = Uploader.request(
            ALBUM_URL + '/' + album_hash + '/add',
            method='post',
            data={
                'deletehashes': _prepare_deletehashes(deletehashes),
            },
    )
    return _is_success(response)

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

    Returns the json response containing the image information
                See: https://api.imgur.com/models/image
            or None if the upload fails
            or False if the bot is imgur ratelimited or should otherwise retry
                (eg. 500-level status code)
    """

    logger.id(logger.info, Uploader.ME, 'Uploading image')
    if logger.is_enabled_for(logger.DEBUG):
        msg = ['']
        if album_hash:
            msg.append('album: \'{album_hash}\'')
        if type_:
            msg.append('type: \'{type_}\'')
        if name:
            msg.append('name: \'{name}\'')
        if title:
            msg.append('title: \'{title}\'')
        if description:
            msg.append('description: \'{description}\'')
        logger.id(logger.debug, Uploader.ME,
                '\n'.join(msg) + '\n',
                album_hash=album_hash,
                type_=type_,
                name=name,
                title=title,
                description=description,
        )

    # TODO? check the 'type_' parameter?
    fd = None
    path = resolve_path(image)
    if os.path.exists(path):
        try:
            fd = open(path, 'rb')
        except (IOError, OSError):
            logger.id(logger.warn, Uploader.ME,
                    'Failed to upload \'{path}\'!',
                    path=path,
                    exc_info=True,
            )

    try:
        response = Uploader.request(
                IMAGE_URL,
                method='post',
                files={'image': fd} if fd else None,
                data={
                    # the image parameter _should_ be either a url or base64
                    # data if fd was not initialized
                    'image': image if not fd else None,
                    'album': album_hash,
                    'type': type_,
                    'name': name,
                    'title': title,
                    'description': description,
                },
        )
    finally:
        if hasattr(fd, 'close'):
            fd.close()

    success = _is_success(response)
    if success:
        try:
            return response.json()
        except ValueError:
            logger.id(logger.warn, Uploader.ME,
                    'Image upload may have failed: bad json response!',
                    exc_info=True,
            )
    return success

# ######################################################################

def update_image(image_hash, title=None, description=None):
    """
    Updates the title and/or description of an image

    image_hash (str) - the image deletehash to update
    title (str, optional) - the title of the image
    description (str, optional) - the description of the image

    Returns True if the image is successfully updated
            or None if the image is not successfully updated
            or False if the bot is imgur ratelimited or should otherwise retry
                (eg. 500-level status code)
    """

    msg = []
    if title:
        msg.append('title: \'{title}\'')
    if description:
        msg.append('description: \'{description}\'')
    logger.id(logger.info, Uploader.ME,
            'Updating image \'{image_hash}\'{colon}{msg}',
            image_hash=image_hash,
            colon=(':\n' if msg else ''),
            msg='\n'.join(msg),
            title=title,
            description=description,
    )

    response = Uploader.request(
            IMAGE_URL + '/' + image_hash,
            method='post',
            data={
                'title': title,
                'description': description,
            },
    )
    return _is_success(response)


