import abc

from six import add_metaclass

from src import reddit


@add_metaclass(abc.ABCMeta) # XXX: not technically abstract at the moment
class RedditInstanceMixin(object):
    """
    A simple mixin that initializes the .cfg and ._reddit member variables
    """

    def __init__(self, cfg, rate_limited, rate_limit_time):
        """
        cfg (config.Config) - the config instance
        rate_limited (multiprocessing.Event) - the process-safe Event
                used to flag whether we are rate-limited by reddit
        rate_limit_time (multiprocessing.Value) - the static number of seconds
                the rate-limit will last
        """
        self.cfg = cfg
        self.__rate_limited = rate_limited
        self.__rate_limit_time = rate_limit_time

    @property
    def _reddit(self):
        """
        Lazy-loaded reddit instance
        """
        try:
            instance = self.__reddit_instance
        except AttributeError:
            instance = reddit.Reddit(
                    self.cfg, self.__rate_limited, self.__rate_limit_time,
            )
            self.__reddit_instance = instance

        return instance


__all__ = [
        'RedditInstanceMixin',
]

