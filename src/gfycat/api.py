import json

from six import string_types
from six.moves.urllib.parse import quote_plus

from .constants import (
        ALBUMS_URL,
        FETCH_URL,
        FETCH_STATUS_URL,
)
from .uploader import Uploader
from src.util import (
        logger,
        remove_duplicates,
)


def _resolve_album_id(user_or_album_id):
    """
    Returns the album_id string for the specified username or album_id
            or None if no such album exists

    * Note: this may incur a gfycat network hit
    """
    try:
        album_id = Uploader.albums[user_or_album_id]
    except KeyError:
        album_id = None
        data = Uploader.albums.cache_data()
        if data:
            try:
                album_id = Uploader.albums[user_or_album_id]
            except KeyError:
                if Uploader.albums.is_id(user_or_album_id):
                    # album_id specified
                    album_id = user_or_album_id

        else:
            # TODO? create album?
            logger.id(logger.debug, Uploader.ME,
                    'No such album: \'{album_id}\'',
                    album_id=user_or_album_id,
            )

    return album_id

# ######################################################################

def create_album(album_name):
    """
    Creates an album if it does not already exist

    Returns True if the album is successfully created or already existed
    """
    exists = album_name in Uploader.albums
    if not exists:
        if Uploader.albums.cache_data():
            exists = album_name in Uploader.albums
    if exists:
        return True

    success = False

    logger.id(logger.info, Uploader.ME,
            'Creating album: \'{album_name}\' ...',
            album_name=album_name,
    )

    root_album_id = Uploader.root_album_id
    if root_album_id:
        response = Uploader.request_authed(
                ALBUMS_URL.format(root_album_id),
                method='post',
                data=json.dumps({
                    'folderName': album_name,
                })
        )
        if hasattr(response, 'status_code') and response.status_code == 200:
            # eg. '"9d179cab967b3bf6dd5bf861145ba72b"'
            album_id = response.text
            if album_id:
                album_id = album_id.strip('"')

                logger.id(logger.debug, Uploader.ME,
                        'Created album \'{album_name}\''
                        ' (id=\'{album_id}\')',
                        album_name=album_name,
                        album_id=album_id,
                )
                logger.id(logger.debug, Uploader.ME,
                        'Setting album link ...',
                )

                # XXX: this endpoint is not documented but their desktop
                # web application hits it to set the link. without this,
                # the album is not linkable and behaves strangely.
                name = Uploader.request_authed(
                        ALBUMS_URL.format(album_id) + '/name',
                        method='put',
                        data=json.dumps({
                            'value': quote_plus(album_name),
                        }),
                )
                if hasattr(name, 'status_code') and name.status_code == 200:
                    Uploader.albums.cache_data()
                    success = True
                else:
                    logger.id(logger.info, Uploader.ME,
                            'Failed to set album (\'{album_id}\')'
                            ' link to {album_name}!',
                            album_id=album_id,
                            album_name=album_name,
                    )

            else:
                logger.id(logger.debug, Uploader.ME,
                        'Cannot set album \'{album_name}\' link:'
                        ' response did not include album id!',
                        album_name=album_name,
                )

    else:
        # this may be spammy depending on how this method is called
        logger.id(logger.debug, Uploader.ME,
                'Cannot create album \'{album_name}\':'
                ' failed to lookup root album id',
                album_name=album_name,
        )

    return success

# ######################################################################

def add_to_album(user_or_album_id, to_add):
    """
    Adds the gfynames (eg. ['ThatRaggedCondor', 'FirmWarlikeChafer', ...]
    to the album.

    * Note: the added gfycats order is NOT preserved

    user_or_album_id (str) - the album title (username) or album_id string
                of the album to add gfycats to
    to_add (list) - a list of gfyname strings to add to the the album

    Returns True if the gfycats were successfully added to the album
                or if the specified gfycats were already in the album
            or False if adding the gfycats failed
            or None if the album does not exist
    """

    logger.id(logger.info, Uploader.ME,
            'Adding to album \'{album_id}\': {color} ...',
            album_id=user_or_album_id,
            color=to_add,
    )

    album_id = _resolve_album_id(user_or_album_id)
    if not album_id:
        return None

    success = False
    response = Uploader.request_authed(ALBUMS_URL.format(album_id))
    if hasattr(response, 'status_code') and response.status_code == 200:
        failed_msg = 'Failed to add #{num} gfycat{plural} to album'
        try:
            data = response.json()
        except ValueError:
            logger.id(logger.warn, Uploader.ME,
                    '{fail}:'
                    ' could not determine existing gfycats in album!',
                    num=len(to_add),
                    plural=('' if len(to_add) == 1 else 's'),
                    exc_info=True,
            )

        else:
            try:
                if int(data['gfyCount']) > 0:
                    # TODO: check g['copyrightClaimant'] (and re-upload(?))
                    published = [g['gfyName'] for g in data['publishedGfys']]
                else:
                    published = []
            except (KeyError, TypeError, ValueError):
                logger.id(logger.warn, Uploader.ME,
                        '{fail}: response structure changed!',
                        num=len(to_add),
                        plural=('' if len(to_add) == 1 else 's'),
                        exc_info=True,
                )

            else:
                orig_list = to_add
                pruned_list = [
                        gfyname for gfyname in to_add
                        if gfyname not in published
                ]
                if len(orig_list) > len(pruned_list):
                    # gfynames already in the album were specified
                    pruned = [
                            gfyname for gfyname in to_add
                            if gfyname not in pruned_list
                    ]
                    logger.id(logger.debug, Uploader.ME,
                            'Pruned #{num} gfyname{plural}: {color}',
                            num=len(pruned),
                            plural=('' if len(plural) == 1 else 's'),
                            color=pruned,
                    )

                if pruned_list:
                    add = Uploader.request_authed(
                            ALBUMS_URL.format(album_id),
                            method='patch',
                            data=json.dumps({
                                'action': 'add_to_album',
                                # XXX: the gfyids MUST be lowercase
                                'gfy_ids': [
                                    gfyname.lower() for gfyname in pruned_list
                                ],
                            }),
                    )
                    success = (
                            hasattr(add, 'status_code')
                            and add.status_code == 200
                    )
                    if success:
                        logger.id(logger.info, Uploader.ME,
                                'Successfully added to album: {color}',
                                color=to_add,
                        )

                else:
                    logger.id(logger.info, Uploader.ME,
                            'All gfynames already in album: skipping.',
                    )
                    success = True

    return success

# ######################################################################

def _put_album(user_or_album_id, prop, value):
    """
    Sets the respective albums meta data endpoint. See:
    https://developers.gfycat.com/api/#albums

    user_or_album_id (str) - the album title (username) or album_id string
                of the album to set the property of
    prop (str) - the string album property to set. should be one of:
                title, description, nsfw, published, order
    value - the new value to set the property to (see the api documentation
                for more information)

    Returns True if the album property is successfully set
            or False if setting the property fails
            or None if the album does not exist
    """

    prop = prop.strip().lower()
    if not isinstance(value, string_types) and hasattr(value, '__iter__'):
        value_str = '#{0} gfycat{1}'.format(
                len(value),
                '' if len(value) == 1 else 's',
        )
    else:
        value_str = '\'{0}\''.format(value)

    logger.id(logger.info, Uploader.ME,
            'Setting album \'{album_id}\' {prop}: {value_str}',
            album_id=user_or_album_id,
            prop=prop,
            value_str=value_str,
    )
    if not isinstance(value, string_types) and hasattr(value, '__iter__'):
        # this may be spammy
        logger.id(logger.debug, Uploader.ME,
                'value:\n{color}\n',
                color=value,
        )

    album_id = _resolve_album_id(user_or_album_id)
    if not album_id:
        return None

    success = False
    response = Uploader.request_authed(
            # XXX: assumes the PUT endpoint is a "child" of the albums
            # endpoint (eg. /me/albums/{albumId}/order)
            ALBUMS_URL.format(album_id) + '/' + prop,
            method='put',
            data=json.dumps({
                'value': value,
            }),
    )
    if hasattr(response, 'status_code') and response.status_code == 200:
        logger.id(logger.info, Uploader.ME,
                'Successfully set {prop} of album: {value_str}',
                prop=prop,
                value_str=value_str,
        )
        success = True

    else:
        logger.id(logger.info, Uploader.ME,
                'Failed to set {prop} of album to {value_str}',
                prop=prop,
                value_str=value_str,
        )

    return success

# ######################################################################

def set_album_title(user_or_album_id, title):
    """
    Sets the album title

    user_or_album_id (str) - the album title (username) or album_id string
                of the album to set the title of
    title (str) - the new title of the album

    Returns True if the album's title is successfully set
            or False if setting the title fails
            or None if the album does not exist
    """
    return _put_album(user_or_album_id, 'title', title)

# ######################################################################

def set_album_description(user_or_album_id, description):
    """
    Sets the album description

    user_or_album_id (str) - the album title (username) or album_id string
                of the album to set the title of
    description (str) - the new description of the album

    Returns True if the album's description is successfully set
            or False if setting the description fails
            or None if the album does not exist
    """
    return _put_album(user_or_album_id, 'description', description)

# ######################################################################

def set_album_nsfw_flag(user_or_album_id, nsfw=1):
    """
    Sets the album nsfw flag

    user_or_album_id (str) - the album title (username) or album_id string
                of the album to set the nsfw flag of
    description (str) - the new nsfw flag of the album

    Returns True if the album's nsfw flag is successfully set
            or False if setting the nsfw flag fails
            or None if the album does not exist
    """
    return _put_album(user_or_album_id, 'nsfw', nsfw)

# ######################################################################

def set_album_published(user_or_album_id, published=0):
    """
    Sets the album public/hidden flag

    user_or_album_id (str) - the album title (username) or album_id string
                of the album to set the public/hidden flag of
    description (str) - the new public/hidden flag of the album

    Returns True if the album's public/hidden flag is successfully set
            or False if setting the public/hidden flag fails
            or None if the album does not exist
    """
    return _put_album(user_or_album_id, 'published', published)

# ######################################################################

def set_album_order(user_or_album_id, order_list):
    """
    Sets the album gfyname order to the specified order

    user_or_album_id (str) - the album title (username) or album_id string
                of the album to add gfycats to
    order_list (list) - a list of gfyname strings to set the album order to

    Returns True if the gfycats were successfully added to the album
                or if the specified gfycats were already in the album
            or False if adding the gfycats failed
            or None if the album does not exist
    """
    # XXX: the gfynames in order_list MUST be lowercase
    order_list = [gfyname.lower() for gfyname in order_list]
    return _put_album(user_or_album_id, 'order', order_list)

# ######################################################################

def fetch_url(url, title):
    """
    Fetches a remote url to create a new gfycat through their api (this
    does not store the url data locally).

    Returns the gfyname if the fetch request is successful
            or None if the fetch request fails
    """
    gfyname = None

    logger.id(logger.info, Uploader.ME,
            'Triggering gfycat fetch: \'{title}\'',
            title=title,
    )
    logger.id(logger.debug, Uploader.ME,
            'fetch url: \'{url}\'',
            url=url,
    )

    response = Uploader.request_authed(FETCH_URL,
            method='post',
            data=json.dumps({
                'fetchUrl': url,
                'title': title,
                'noMd5': True,
                'nsfw': 1,
                'private': True,
            }),
    )
    if hasattr(response, 'status_code') and response.status_code == 200:
        try:
            data = response.json()
        except ValueError:
            logger.id(logger.warn, Uploader.ME,
                    'Failed to upload \'{title}\': bad response!',
                    title=title,
                    exc_info=True,
            )

        else:
            try:
                is_ok = data['isOk']
                if is_ok:
                    gfyname = data['gfyname']
            except KeyError:
                logger.id(logger.warn, Uploader.ME,
                        'Gfycat fetch response structure changed!',
                        exc_info=True,
                )
                logger.id(logger.debug, Uploader.ME,
                        'data:\n{pprint}\n',
                        pprint=data,
                )
            else:
                logger.id(logger.info, Uploader.ME,
                        'Upload in progress: \'{gfyname}\'',
                        gfyname=gfyname,
                )

    return gfyname

# ######################################################################

def fetch_status(gfyname):
    """

    Returns (STATUS_*, message) where
                STATUS_* - one of the STATUS_* "enums"
                message - string message describing the status
            or False if the request fails or there is a problem parsing the
                response
            or None if gfyname is invalid or there is no active fetch for
                the gfyname
    """
    if not isinstance(gfyname, string_types):
        return None

    logger.id(logger.debug, Uploader.ME,
            'Requesting fetch status for \'{gfyname}\' ...',
            gfyname=gfyname,
    )

    status = False
    message = None
    response = Uploader.request(FETCH_STATUS_URL.format(gfyname))
    if response is not None and response.status_code == 200:
        try:
            data = response.json()
        except ValueError:
            logger.id(logger.warn, Uploader.ME,
                    'Unexpected fetch status response!',
                    exc_info=True,
            )

        else:
            try:
                task = data['task'].strip().lower()
            except (AttributeError, KeyError):
                logger.id(logger.warn, Uploader.ME,
                        'Fetch status response structure changed!',
                        exc_info=True,
                )

            else:
                # https://developers.gfycat.com/api/#checking-the-status-of-your-upload
                if task == 'encoding':
                    status = Uploader.STATUS_INPROGRESS
                    message = task
                elif task == 'complete':
                    status = Uploader.STATUS_COMPLETE
                    message = task
                elif 'notfound' in task:
                    # 'NotFoundo' is the task if the gfyname is not an
                    # active fetch. I guess some intern thought this was
                    # funny?
                    status = None
                elif task == 'error':
                    try:
                        # XXX: I assume the error code is an int but
                        # "cast" it to a str just in case it isn't
                        code = str(data['errorMessage']['code'])
                        message = data['errorMessage']['description']
                    except KeyError:
                        logger.id(logger.warn, Uploader.ME,
                                'Fetch status error response structure'
                                ' changed!',
                                exc_info=True,
                        )

                    else:
                        logger.id(logger.debug, Uploader.ME,
                                'Fetch error status:'
                                '\n\tcode: \'{code}\''
                                '\n\tdescription: \'{message}\'',
                                code=code,
                                message=message,
                        )

                        # https://developers.gfycat.com/api/#errors
                        if code == '10500': # failed to create gfycat
                            status = Uploader.STATUS_FAILED
                        elif code == '20500': # error fetching file
                            status = Uploader.STATUS_ERROR
                        elif code == '20401': # invalid file permissions
                            status = Uploader.STATUS_INVALID_PERMISSIONS
                        elif code == '20404': # file not found
                            status = Uploader.STATUS_NOT_FOUND
                        elif code == '20400': # invalid file format
                            status = Uploader.STATUS_INVALID_FILE_FORMAT
                        elif code == '20503': # fetch timed out
                            status = Uploader.STATUS_TIMEDOUT

    if not status:
        return status
    return status, message


