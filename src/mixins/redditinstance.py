import abc

from six import add_metaclass


@add_metaclass(abc.ABCMeta) # XXX: not technically abstract at the moment
class RedditInstanceMixin(object):
    """
    A simple mixin that initializes the .cfg and ._reddit member variables
    """

    def __init__(self, cfg, rate_limited):
        """
        cfg (config.Config) - the config instance
        rate_limited (ratelimit.Flag) - the process-safe Event
                used to flag whether we are rate-limited by reddit
        """
        self.cfg = cfg
        self.__rate_limited = rate_limited

    @property
    def _reddit(self):
        """
        Lazy-loaded reddit instance
        """
        try:
            instance = self.__reddit_instance
        except AttributeError:
            from src import reddit

            if hasattr(self, '_killed'):
                reddit.Reddit._killed = self._killed
            else:
                logger.id(logger.debug, self,
                        'Could not set Reddit._killed: no ._killed member!',
                )
            instance = reddit.Reddit(self.cfg, self.__rate_limited)
            self.__reddit_instance = instance

        return instance


__all__ = [
        'RedditInstanceMixin',
]

