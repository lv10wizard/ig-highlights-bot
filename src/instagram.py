import re
import os
from urlparse import urlparse

from utillib (
        logger,
        soup,
)

from src import (
        history,
)


# https://stackoverflow.com/a/33783840
# GET json: https://instagram.com/{user}/media
#   {
#       'status': 'ok',
#       'items': [
#           {
#               'alt_media_url': None,
#               'can_delete_comments': False,
#               'can_view_comments': True,
#               'caption': { ... },
#               'code': 'BYtcWH_j31M',
#               'comments': { ... },
#               'created_time': '1504723393',
#               'id': '1598058108499754316_3224256723',
#               'images': { ... },
#               'likes': {
#                   'count': 2539,
#                   'data': [ ... ],
#               },
#               'link': 'https://www.instagram.com/p/BYtcWH_j31M',
#               'location': '...',
#               'type': 'image',
#               'user': {
#                   'full_name': '...',
#                   'id': '...',
#                   'profile_picture': '...',
#                   'username': '...',
#               },
#           },
#           ...
#           (n = 20)
#       ],
#   }
# GET https://instagram.com/{user}/media/?max_id={last_id}
#       where {last_id} is the last id from the previous json fetch
#       ie, data['items'][-1]['id']

# TODO:
#   1. fetch all(?) media for a given user
#       a. keep file of request by time
#           (DO NOT EXCEED 3k/hr -- API rate limit = 5k / hr)
#       b. handle 404 & empty data['items']
#               - empty => non-user page => cache path/link to file to prevent future hits?
#   2. sort by likes-count
#   3? write data to file (keep as per-user cache to lower #hits to instagram)
#       a. maybe consider cache file stale if elapsed time since get > T

class Instagram(object):
    """
    """

    @staticmethod
    def _parse_user_from_link(link):
        user = None
        parsed = urlparse(link)
        link_path = filter(None, parsed.path.split('/'))
        if len(link_path) == 1:
            user = link_path[0]
        return user

    def __init__(self, link):
        self.history = history.History()
        self.user = Instagram._parse_user_from_link(link)
        self.link = None
        if self.user:
            # hard-code the landing page link to sanitize any trailing queries
            # or paths
            self.link = 'https://www.instagram.com/{0}'.format(self.user)
        self.media = None # TODO: fetch data & parse responses

    def __str__(self):
        return self.__repr__()

    @property
    def valid(self):
        return bool(self.user) and bool(self.media)


__all__ = [
        'Instagram',
]

