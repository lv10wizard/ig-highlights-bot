import multiprocessing
import os

from utillib import logger

from src import reddit
from src.database import BlacklistDatabase


class Blacklist(object):
    """
    Interface between application <-> BlacklistDatabase

    This class provides convenience methods specifically for BlacklistDatabase
    """

    def __init__(self, cfg):
        self.__database = BlacklistDatabase(
                path=cfg.blacklist_db_path,
                cfg=cfg,
                do_seed=(not os.path.exists(cfg.blacklist_db_path)),
        )
        self.__lock = multiprocessing.RLock()

    def __str__(self):
        return self.__class__.__name__

    @staticmethod
    def __get_blacklist_type(name, prefix):
        """
        Attempts to determine the corresponding BlacklistDatabase.TYPE_* from
        the name prefix (eg. 'u/foobar' -> TYPE_USER)

        Returns BlacklistDatabase.TYPE_* constant
        """
        name_type = None
        def get_type(prefix):
            if prefix:
                if reddit.is_subreddit_prefix(prefix):
                    name_type = BlacklistDatabase.TYPE_SUBREDDIT
                elif reddit.is_user_prefix(prefix):
                    name_type = BlacklistDatabase.TYPE_USER

        name_type = get_type(prefix)
        if not name_type:
            prefix, name = reddit.split_prefixed_name(name)
            name_type = get_type(prefix)

        return name_type

    def add(self, name, prefix=None, is_tmp=False):
        """
        Adds the name to the blacklist database.
        If the name is temporarily blacklisted, it is flagged to be made
        permanent (so long as is_tmp != True).

        name (str) - prefixed or raw (no prefix) name string
            eg. 'u/foobar' or 'AskReddit'
        prefix (str, optional) - either PREFIX_SUBREDDIT or PREFIX_USER
            if name is not prefixed and no prefix is specified, then add will
            fail.
        is_tmp (bool, optional) - whether the ban is temporary

        Returns True if name was successfully added to the database
        """
        success = False
        name_type = Blacklist.__get_blacklist_type(name, prefix)
        if not name_type:
            logger.prepend_id(logger.debug, self,
                    'Could not add {color_name} to blacklist:'
                    ' failed to determine blacklist type'
                    ' (name=\'{name}\', prefix=\'{prefix}\')',
                    color_name=name,
                    name=name,
                    prefix=prefix,
            )

        else:
            _, name_raw = reddit.split_prefixed_name(name)

            with self.__lock:
                is_blacklisted = self.__database.is_blacklisted(
                        name_raw, name_type
                )
                temporary = self.__database.is_blacklisted_temporarily(name_raw)

                if is_blacklisted and temporary:
                    if is_tmp:
                        # tried to ban temporarily but was already temporarily
                        # banned
                        logger.prepend_id(logger.debug, self,
                                'Could not temporarily add {color_name} to'
                                ' blacklist: already temporarily blacklisted.',
                                color_name=name_raw,
                        )

                    else:
                        # flag the record to be made permanent
                        time_left = self.__database.blacklist_time_left_seconds(
                                name_raw,
                        )
                        logger.prepend_id(logger.debug, self,
                                'Flagging {color_name}\'s ban to be made'
                                ' permanent ({time} remaining)',
                                color_name=name_raw,
                                time=time_left,
                        )
                        self.__database.set_make_permanent(name, name_type)
                        success = True

                elif not is_blacklisted:
                    logger.prepend_id(logger.debug, self,
                            'Adding {color_name} {tmp}to blacklist'
                            color_name=name_raw,
                            tmp=('temporarily ' if is_tmp else ''),
                    )
                    self.__database.insert(name_raw, name_type, is_tmp)
                    # XXX: assumes insert was successful
                    success = True

                else:
                    logger.prepend_id(logger.debug, self,
                            'Could not add {color_name} to blacklist:'
                            ' already blacklisted.',
                            color_name=name_raw,
                    )

                if success:
                    self.__database.commit()

        return success

    def remove(self, name, prefix=None):
        """
        Removes the the name from the database.
        Will not remove the name if it is a temporary ban (unless force is True)

        name (str) - prefixed or raw (no prefix) name string
            eg. 'u/foobar' or 'AskReddit'
        prefix (str, optional) - either PREFIX_SUBREDDIT or PREFIX_USER
            if name is not prefixed and no prefix is specified, then remove will
            fail.
        """
        success = False
        name_type = Blacklist.__get_blacklist_type(name, prefix)
        if not name_type:
            logger.prepend_id(logger.debug, self,
                    'Could not remove {color_name} from blacklist:'
                    ' failed to determine blacklist type'
                    ' (name=\'{name}\', prefix=\'{prefix}\')',
                    color_name=name,
                    name=name,
                    prefix=prefix,
            )

        else:
            _, name_raw = reddit.split_prefixed_name(name)

            # I'm not 100% certain this requires locking.. maybe in extremely
            # rare situations.
            with self.__lock:
                time_left = self.__database.blacklist_time_left_seconds(
                        name_raw
                )
                if time_left < 0:
                    logger.prepend_id(logger.debug, self,
                            'Removing {color_name} from blacklist',
                            color_name=name_raw,
                    )
                    self.__database.delete(name_raw, name_type)
                    # XXX: assumes delete was successful
                    success = True

                elif time_left > 0:
                    logger.prepend_id(logger.debug, self,
                            'Clearing flag to make {color_name}\'s ban'
                            ' permanent ({time} remaining)',
                            color_name=name_raw,
                            time=time_left,
                    )
                    self.__database.clear_make_permanent(name_raw, name_type)
                    success = True

                if success:
                    self.__database.commit()

        return success

    def is_blacklisted_thing(self, thing):
        """
        Returns the prefixed name of the banned thing (Comment, Submission, etc)
            if it is blacklisted -- either posted by a blacklisted user or in a
            blacklisted subreddit

            ie, if the author is banned, returns 'u/{username}'
                if the subreddit is banned, returns 'r/{subreddit}'

        Returns False if not blacklisted
        """
        try:
            subreddit = thing.subreddit.display_name
            if self.__database.is_blacklisted_subreddit(subreddit):
                return reddit.prefix_subreddit(subreddit)

            author = thing.author.name
            if self.__database.is_blacklisted_user(author):
                return reddit.prefix_user(author)

        except AttributeError:
            # eg. deleted comment
            pass

        return False

    def is_blacklisted_name(self, name, prefix=None):
        """
        Returns True if the name (prefixed or non-prefixed) is blacklisted
            eg. 'u/foobar' or 'AskReddit'
        """
        name_type = Blacklist.__get_blacklist_type(name, prefix)
        if not name_type:
            logger.prepend_id(logger.debug, self,
                    'Could not determine if {color_name} is blacklisted:'
                    ' failed to determine blacklist type'
                    ' (name=\'{name}\', prefix=\'{prefix}\')',
                    color_name=name,
                    name=name,
                    prefix=prefix,
            )
            return False

        parsed_prefix, name_raw = reddit.split_prefixed_name(name)
        if (
                # check both in case one if a random string
                reddit.is_subreddit_prefix(prefix)
                or reddit.is_subreddit_prefix(parsed_prefix)
        ):
            return self.__database.is_blacklisted_subreddit(name_raw)

        if (
                reddit.is_user_prefix(prefix)
                or reddit.is_user_prefix(parsed_prefix)
        ):
            return self.__database.is_blacklisted_user(name_raw)

        return False

    def time_left_seconds_name(self, name, prefix=None):
        """
        Returns the time remaining (seconds) of a temporary ban
                0 if either not blacklisted (or other failure)
        """
        name_type = Blacklist.__get_blacklist_type(name, prefix)
        if not name_type:
            logger.prepend_id(logger.debug, self,
                    'Could not determine time remaining on {color_name}\'s'
                    ' blacklisted: failed to determine blacklist type'
                    ' (name=\'{name}\', prefix=\'{prefix}\')',
                    color_name=name,
                    name=name,
                    prefix=prefix,
            )
            return 0

        parsed_prefix, name_raw = reddit.split_prefixed_name(name)
        return self.__database.blacklist_time_left_seconds(name_raw)


__all__ = [
        'Blacklist',
]

