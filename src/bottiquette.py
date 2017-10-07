import json
import time

from prawcore.exceptions import PrawcoreException

from src.config import parse_time
from src.util import logger


class RobotsTxt(object):
    """
    Wrapper class which fetches
    https://www.reddit.com/r/Bottiquette/wiki/robots_txt_json
    """

    UPDATE_THRESHOLD = parse_time('1d')

    def __init__(self, reddit_obj):
        self._bad_keys = set()
        self._valid = True
        self._last_update = -1
        # XXX: not a RedditInstanceMixin because there it doesn not require a
        # new reddit object
        self._reddit = reddit_obj

    def __str__(self):
        return self.__class__.__name__

    def __getitem__(self, key):
        """
        Expose key access notation (ie, dict[key])
        """
        try:
            return self._robots_json[key]

        except KeyError:
            if key not in self._bad_keys:
                # only log once per key to prevent log spam
                logger.id(logger.warn, self,
                        'No key: \'{key}\' in robots_txt_json!',
                        key=key,
                        exc_info=True,
                )
                self._bad_keys.add(key)
            return []

    def __get_data(self):
        result = {}
        if not self._valid:
            return result

        logger.id(logger.debug, self,
                'Updating from Bottiquette\'s robots_txt_json ...',
        )

        # TODO: determine if this is a network hit -> yes: place in try
        wiki = self._reddit.subreddit('Bottiquette').wiki['robots_txt_json']
        try:
            robots_txt = wiki.content_md

        except PrawcoreException:
            # don't bother retrying; the wiki does not seem to be updated very
            # often anyway (it may be defunct at this point)
            # XXX: don't invalidate future fetches because the content may still
            # be fetchable. we're retrying so infrequently that hitting a bad
            # endpoint shouldn't matter.
            logger.id(logger.warn, self,
                    'Failed to get Bottiquette\'s robots_txt_json!',
                    exc_info=True,
            )

        else:
            try:
                result = json.loads(robots_txt)
            except ValueError:
                logger.id(logger.warn, self,
                        'Could not parse robots_txt_json!'
                        ' Disabling future updates ...',
                        exc_info=True,
                )
                logger.id(logger.debug, self,
                        'robots_txt_json:\n{robots_txt_json}\n\n',
                        robots_txt_json=robots_txt,
                )
                # the wiki is broken; prevent future fetches
                self._valid = False

        return result

    @property
    def _robots_json(self):
        try:
            robots_json = self.__the_robots_json
        except AttributeError:
            robots_json = {}

        elapsed = time.time() - self._last_update
        if elapsed > RobotsTxt.UPDATE_THRESHOLD:
            # fetch or re-fetch the robots_txt_json page
            # XXX: fallback to the previous value in case the get fails
            robots_json = self.__get_data() or robots_json
            self.__the_robots_json = robots_json
            self._last_update = time.time()

        return robots_json

    @property
    def comments_only(self):
        """
        List of subreddits where bots are only allowed to make comments
        """
        return self['comments-only']

    @property
    def posts_only(self):
        """
        List of subreddits where bots can only make posts(?)
        """
        return self['posts-only']

    @property
    def disallowed(self):
        """
        List of subreddits that do not want bots
        """
        return self['disallowed']

    @property
    def permission(self):
        """
        List of subreddits where bots require permission to reply/post(?)
        """
        return self['permission']


__all__ = [
        'RobotsTxt',
]

