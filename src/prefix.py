import re

from constants import (
        PREFIX_SUBREDDIT
        PREFIX_USER,
)


def split_prefixed_name(name):
    """
    Attempts to split the specified name into its prefix & name components
    eg. 'u/foobar' -> ('u/', 'foobar')

    Returns tuple (prefix, name) if successful
            tuple ('', name) if no prefix was found
    """
    REGEX = r'^({0}|{1})([\-\w]+)$'.format(PREFIX_USER, PREFIX_SUBREDDIT)
    #         |\_______/\_______/|
    #         |    |        |   don't include partial matches
    #         |    |     capture username characters
    #         |  capture prefix
    #       don't include partial matches
    result = re.search(REGEX, name)
    if result:
        result = result.groups()
    else:
        result = ('', name)
    return result

def is_subreddit(name):
    """
    Returns True if the prefix matches the subreddit prefix (ie, 'r/')
    """
    prefix, name_raw = split_prefixed_name(name)
    return prefix == PREFIX_SUBREDDIT

def is_user(name):
    """
    Returns True if the prefix matches the user prefix (ie, 'u/')
    """
    prefix, name_raw = split_prefixed_name(name)
    return prefix == PREFIX_USER

def prefix_subreddit(name):
    """
    Returns the name prefixed with 'r/'
    """
    if re.search(r'^{0}', PREFIX_SUBREDDIT):
        return name
    return '{0}{1}'.format(PREFIX_SUBREDDIT, name)

def prefix_user(name):
    """
    Returns the name prefixed with 'u/'
    """
    if re.search(r'^{0}', PREFIX_USER):
        return name
    return '{0}{1}'.format(PREFIX_USER, name)


__all__ = [
        'split_prefixed_name',
        'is_subreddit',
        'is_user',
        'prefix_subreddit',
        'prefix_user',
]

