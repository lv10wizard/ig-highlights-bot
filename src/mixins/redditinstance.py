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
        self._reddit = reddit.Reddit(cfg, rate_limited, rate_limit_time)


__all__ = [
        'RedditInstanceMixin',
]

