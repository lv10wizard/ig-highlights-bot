import multiprocessing
import os

from six import string_types

from src import reddit
from src.database import (
        BadActorsDatabase,
        BlacklistDatabase,
        UniqueConstraintFailed,
)
from src.util import logger


class Blacklist(object):
    """
    Interface between application <-> BlacklistDatabase

    This class provides convenience methods specifically for BlacklistDatabase
    """

    def __init__(self, cfg):
        self.cfg = cfg
        self.__badactors = BadActorsDatabase(cfg)
        self.__database = BlacklistDatabase(cfg, do_seed=True)
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
            result = None
            if prefix:
                if reddit.is_subreddit_prefix(prefix):
                    result = BlacklistDatabase.TYPE_SUBREDDIT
                elif reddit.is_user_prefix(prefix):
                    result = BlacklistDatabase.TYPE_USER

                # commenting out not-very-useful logging spam
                # (this may be useful in the future to help in solving blacklist
                #  bugs)
                # logger.id(logger.debug, __name__,
                #         'name_type={color_nametype} for prefix=\'{prefix}\'',
                #         color_nametype=result,
                #         prefix=prefix,
                # )
            return result

        name_type = get_type(prefix)

        if not name_type:
            prefix, name = reddit.split_prefixed_name(name)
            name_type = get_type(prefix)

        return name_type

    def add(self, name, prefix=None, tmp=False):
        """
        Adds the name to the blacklist database.
        If the name is temporarily blacklisted, it is flagged to be made
        permanent (so long as tmp != True).

        name (str) - prefixed or raw (no prefix) name string
            eg. 'u/foobar' or 'AskReddit'
        prefix (str, optional) - either PREFIX_SUBREDDIT or PREFIX_USER
            if name is not prefixed and no prefix is specified, then add will
            fail.
        tmp (bool, optional) - whether the ban is temporary

        Returns True if name was successfully added to the database
        """

        msg = ['Adding {thing_name}; tmp=\'{tmp}\'']
        if prefix:
            msg.append(', prefix=\'{prefix}\'')
        msg.append(' ...')
        logger.id(logger.info, self,
                ''.join(msg),
                thing_name=name,
                tmp=tmp,
                prefix=prefix,
        )

        success = False
        name_type = Blacklist.__get_blacklist_type(name, prefix)
        if not name_type:
            logger.id(logger.warn, self,
                    'Could not add {color_name} to blacklist:'
                    ' failed to determine blacklist type'
                    ' (name=\'{name_arg}\', prefix=\'{prefix}\')',
                    color_name=name,
                    name_arg=name,
                    prefix=prefix,
            )

        else:
            _, name_raw = reddit.split_prefixed_name(name)
            prefixed_name = reddit.prefix(name_raw, name_type)

            with self.__lock:
                is_blacklisted = self.__database.is_blacklisted(
                        name_raw, name_type
                )
                temporary = self.__database.is_blacklisted_temporarily(name_raw)

                if is_blacklisted and temporary:
                    if tmp:
                        # tried to ban temporarily but was already temporarily
                        # banned
                        logger.id(logger.info, self,
                                'Could not temporarily add {color_name} to'
                                ' blacklist: already temporarily blacklisted.',
                                color_name=prefixed_name,
                        )

                    else:
                        # flag the record to be made permanent
                        time_left = self.__database.blacklist_time_left_seconds(
                                name_raw,
                        )
                        logger.id(logger.info, self,
                                'Flagging {color_name}\'s ban to be made'
                                ' permanent ({time} remaining)',
                                color_name=prefixed_name,
                                time=time_left,
                        )
                        self.__database.set_make_permanent(name, name_type)
                        success = True

                elif not is_blacklisted:
                    logger.id(logger.info, self,
                            'Adding {color_name} {tmp}to blacklist',
                            color_name=prefixed_name,
                            tmp=('temporarily ' if tmp else ''),
                    )
                    try:
                        self.__database.insert(name_raw, name_type, tmp)
                    except UniqueConstraintFailed:
                        logger.id(logger.warn, self,
                                '{color_name} is already blacklisted!',
                                color_name=prefixed_name,
                                exc_info=True,
                        )
                    else:
                        success = True

                else:
                    logger.id(logger.info, self,
                            'Could not add {color_name} to blacklist:'
                            ' already blacklisted.',
                            color_name=prefixed_name,
                    )

                if success:
                    self.__database.commit()

        return success

    def remove(self, name, prefix=None):
        """
        Removes the the name from the database.
        Will not remove the name if it is a temporary ban

        name (str) - prefixed or raw (no prefix) name string
            eg. 'u/foobar' or 'AskReddit'
        prefix (str, optional) - either PREFIX_SUBREDDIT or PREFIX_USER
            if name is not prefixed and no prefix is specified, then remove will
            fail.
        """

        msg = ['Removing {thing_name}']
        if prefix:
            msg.append(', prefix=\'{prefix}\'')
        msg.append(' ...')
        logger.id(logger.info, self,
                ''.join(msg),
                thing_name=name,
                prefix=prefix,
        )

        success = False
        name_type = Blacklist.__get_blacklist_type(name, prefix)
        if not name_type:
            logger.id(logger.warn, self,
                    'Could not remove {color_name} from blacklist:'
                    ' failed to determine blacklist type'
                    ' (name=\'{name_arg}\', prefix=\'{prefix}\')',
                    color_name=name,
                    name_arg=name,
                    prefix=prefix,
            )

        else:
            _, name_raw = reddit.split_prefixed_name(name)
            prefixed_name = reddit.prefix(name_raw, name_type)

            # I'm not 100% certain this requires locking.. maybe in extremely
            # rare situations.
            with self.__lock:
                if self.__database.is_blacklisted(name_raw, name_type):
                    time_left = self.__database.blacklist_time_left_seconds(
                            name_raw
                    )

                    if time_left <= 0:
                        # permanent ban (user or subreddit)
                        logger.id(logger.info, self,
                                'Removing {color_name} from blacklist',
                                color_name=prefixed_name,
                        )
                        self.__database.delete(name_raw, name_type)
                        # XXX: assumes delete was successful
                        success = True

                    elif time_left > 0:
                        # temp ban
                        logger.id(logger.info, self,
                                'Clearing flag to make {color_name}\'s ban'
                                ' permanent ({time} remaining)',
                                color_name=prefixed_name,
                                time=time_left,
                        )
                        self.__database.clear_make_permanent(
                                name_raw, name_type
                        )
                        success = True

                else:
                    logger.id(logger.info, self,
                            '{color_name} is not blacklisted!',
                            color_name=prefixed_name,
                    )

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
            logger.id(logger.warn, self,
                    'Could not determine if {color_name} is blacklisted:'
                    ' failed to determine blacklist type'
                    ' (name=\'{name_arg}\', prefix=\'{prefix}\')',
                    color_name=name,
                    name_arg=name,
                    prefix=prefix,
            )
            return False

        parsed_prefix, name_raw = reddit.split_prefixed_name(name)
        if (
                # check both in case one is a random string
                reddit.is_subreddit_prefix(prefix)
                or reddit.is_subreddit_prefix(parsed_prefix)
        ):
            return self.__database.is_blacklisted_subreddit(name_raw)

        if (
                reddit.is_user_prefix(prefix)
                or reddit.is_user_prefix(parsed_prefix)
        ):
            return self.__database.is_blacklisted_user(name_raw)

        msg = ['Unrecognized prefix for {color_name}:']
        if prefix:
            msg.append('prefix=\'{prefix}\'')
        if parsed_prefix:
            msg.append('parsed_prefix=\'{parsed_prefix}\'')
        logger.id(logger.debug, self,
                ' '.join(msg),
                color_name=name_raw,
                prefix=prefix,
                parsed_prefix=parsed_prefix,
        )

        return False

    def time_left_seconds_name(self, name, prefix=None):
        """
        Returns the time remaining (seconds) of a temporary ban
                0 if either not blacklisted (or other failure)
        """
        name_type = Blacklist.__get_blacklist_type(name, prefix)
        if not name_type:
            logger.id(logger.warn, self,
                    'Could not determine time remaining on {color_name}\'s'
                    ' blacklisted: failed to determine blacklist type'
                    ' (name=\'{name_arg}\', prefix=\'{prefix}\')',
                    color_name=name,
                    name_arg=name,
                    prefix=prefix,
            )
            return 0

        parsed_prefix, name_raw = reddit.split_prefixed_name(name)
        return self.__database.blacklist_time_left_seconds(name_raw)

    def increment_bad_actor(self, thing):
        """
        Increments the thing.author's bad actor count.
        """
        if hasattr(thing, 'author') and bool(thing.author):
            if thing in self.__badactors:
                logger.id(logger.info, self,
                        '{color_author} already flagged as a bad actor for'
                        ' {color_thing}',
                        color_author=thing.author.name,
                        color_thing=reddit.display_id(thing),
                )
                return

            logger.id(logger.info, self,
                    'Incrementing {color_author}\'s bad actor count ...',
                    color_author=thing.author.name,
            )

            permalink = reddit.display_id(thing)
            if not isinstance(permalink, string_types):
                logger.id(logger.debug, self,
                        '{color_thing} has no valid permalink!'
                        ' (permalink={permalink})',
                        color_thing=reddit.display_id(thing),
                        permalink=permalink,
                )
                permalink = None

            try:
                with self.__badactors:
                    self.__badactors.insert(thing, permalink)

            except UniqueConstraintFailed:
                logger.id(logger.warn, self,
                        '{color_author} already flagged as a bad actor for'
                        ' {color_thing}!',
                        color_author=thing.author.name,
                        color_thing=reddit.display_id(thing),
                        exc_info=True,
                )

            else:
                count = self.__badactors.count(thing)
                threshold = self.cfg.bad_actor_threshold
                if count > threshold:
                    logger.id(logger.info, self,
                            '{color_author} over bad actor threshold!'
                            ' ({count} > {threshold})',
                            color_author=thing.author.name,
                            count=count,
                            threshold=threshold,
                    )
                    self.add(thing.author.name, reddit.PREFIX_USER, True)
                    # TODO? delete (deactivate) badactor count for user
                    # > this should already be implicitly handled but it does
                    #   mean that any further bad behavior will attempt to
                    #   temporarily blacklist the user again.


__all__ = [
        'Blacklist',
]

