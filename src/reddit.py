import multiprocessing
import os
import re

import praw
from prawcore.exceptions import (
        Forbidden,
        OAuthException,
)
from utillib import logger

from constants import (
        AUTHOR,
        PREFIX_SUBREDDIT,
        PREFIX_USER,
)
from src import (
        config,
        error_handling,
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
    return is_subreddit_prefix(prefix)

def is_subreddit_prefix(prefix):
    return prefix == PREFIX_SUBREDDIT

def is_user(name):
    """
    Returns True if the prefix matches the user prefix (ie, 'u/')
    """
    prefix, name_raw = split_prefixed_name(name)
    return is_user_prefix(prefix)

def is_user_prefix(prefix):
    return prefix == PREFIX_USER

def prefix_subreddit(name):
    """
    Returns the name prefixed with 'r/'
    """
    return prefix(name, PREFIX_SUBREDDIT)

def prefix_user(name):
    """
    Returns the name prefixed with 'u/'
    """
    return prefix(name, PREFIX_USER)

def prefix(name, prefix):
    if re.search(r'^{0}', prefix):
        return name
    return '{0}{1}'.format(prefix, name)

def pack_subreddits(iterable):
    """
    Returns the multiple subreddit string
    eg. ['AskReddit', 'test', 'help']
     -> 'AskReddit+test+help'

    See:
    https://praw.readthedocs.io/en/latest/code_overview/models/subreddit.html
    """
    return '+'.join(str(i) for i in iterable)

def unpack_subreddits(subreddits_str):
    """
    Returns a set containing each subreddit defined in subreddits_str
    eg. 'AskReddit+test+help'
     -> set(['AskReddit', 'test', 'help'])
    """
    return set(subreddits_str.split('+'))

# ######################################################################

class Reddit(praw.Reddit):
    """
    praw.Reddit wrapper
    """

    NOTSET_TYPE = praw.config._NotSet
    LINE_SEP = '=' * 72

    def __init__(self, cfg, *args, **kwargs):
        self.__cfg = cfg
        self.__error_handler = error_handling.ErrorHandler()

        praw.Reddit.__init__(self,
                site_name=cfg.praw_sitename,
                user_agent=self.user_agent,
                *args, **kwargs
        )

        praw_ini_login = True
        manual_login = False
        # prevent other processes logging while trying to get user input
        with logger.get()._lock:
            logger.prepend_id(logger.debug, self,
                    'Looking up login credentials ...',
            )
            manual_username = self.__try_set_username()
            manual_password = self.__try_set_password()
        manual_login = manual_username or manual_password
        # don't output the praw-ini failure section if neither username
        # nor password are defined in the ini file.
        praw_ini_login = not (manual_username and manual_password)

        # try to auth immediately to catch anything wrong with credentials
        try:
            self.user.me()

        except (Forbidden, OAuthException) as e:
            msg = ['\'{username}\' login failed! Please double check that']
            if praw_ini_login:
                msg.append(
                        'praw.ini ([{section}]) contains the correct'
                        ' login information'
                )
                if manual_login:
                    msg.append('and that')

            if manual_login:
                msg.append('you entered the correct username/password')

            logger.prepend_id(logger.error, self,
                    ' '.join(msg), e, True,
                    username=self.username_raw or '<Not Set>',
                    section=cfg.praw_sitename,
            )

        logger.prepend_id(logger.debug, self,
                '\n\tclient id:  {client_id}'
                '\n\tuser name:  {username}'
                '\n\tuser agent: {user_agent}',
                client_id=self.config.client_id,
                username=self.username_raw,
                user_agent=self.user_agent,
        )

    def __str__(self):
        try:
            pid = os.getpid()
        except OSError:
            pid = None

        result = filter(None, [
            self.__class__.__name__,
            pid and '{0}'.format(pid),
            self.username,
        ])
        return ':'.join(result)

    @property
    def username_raw(self):
        raw = self.config.username
        return raw if not isinstance(raw, NOTSET_TYPE) else None

    @property
    def username(self):
        return prefix_user(self.username_raw) if self.username_raw else None

    @property
    def user_agent(self):
        """
        Memoized user agent string
        """
        try:
            user_agent = self.__user_agent
        except AttributeError:
            version = '0.1' # TODO: read from file
            self.__user_agent = (
                    '{platform}:{appname}:{version} (by {author})'
            ).format(
                    platform=sys.platform,
                    appname=self.__cfg.app_name,
                    version=version,
                    author=prefix_user(AUTHOR),
            )
            user_agent = self.__user_agent
        return user_agent

    def __try_set_username(self):
        """
        Asks the user to enter the bot account username if not defined in
        praw.ini
        """
        did_set = False
        if isinstance(self.config.username, NOTSET_TYPE):
            self.config.username = raw_input('bot account username: ')
            self.__warn_if_wrong_praw_version()
            self._prepare_prawcore()
            did_set = True
        return did_set

    def __try_set_password(self):
        """
        Asks the user to enter the bot account password if it was not defined
        in praw.ini
        """
        did_set = False
        while isinstance(self.config.password, NOTSET_TYPE):
            first = getpass('{0} password: '.format(self.username))
            second = getpass('Re-enter password: ')
            if first == second:
                self.config.password = first

                # https://github.com/praw-dev/praw/blob/master/praw/reddit.py
                # XXX: praw's Config.password is just a member variable; setting
                # it does not actually allow authentication if the password
                # is set after Reddit.__init__
                self.__warn_if_wrong_praw_version()
                # the following call works as of praw 5.1 (may break in later
                # versions)
                self._prepare_prawcore()
                did_set = True
            else:
                logger.prepend_id(logger.warn, self,
                        'Passwords do not match! Please try again.',
                )
        return did_set

    def __warn_if_wrong_praw_version(self):
        major, minor, revision = praw.__version__.split('.')
        try:
            major = int(major)
            minor = int(minor)
            revision = int(revision)
        except ValueError as e:
            # something went horribly wrong
            logger.prepend_id(logger.error, self,
                    'Failed to determine praw version!', e, True,
            )
        else:
            if not (major == 5 and minor == 1 and revision == 0):
                logger.prepend_id(logger.warn, self,
                        'praw version != 5.1.0 (version={ver});'
                        ' authentication may fail!',
                        ver=praw.__version__,
                )

    def display_id(self, thing):
        if hasattr(thing, 'id'):
            if hasattr(thing, 'subreddit_name_prefixed'):
                return '/'.join([thing.subreddit_name_prefixed, thing.id])
            else:
                return thing.id
        return thing

    def display_fullname(self, thing):
        if hasattr(thing, 'fullname'):
            try:
                kinds = self.__kinds
            except AttributeError:
                kinds = {
                        type_prefix: thing_name
                        for thing_name, type_prefix in
                        self.config.kinds.iteritems()
                }
                self.__kinds = kinds

            try:
                thing_type = kinds[thing.fullname.split('_', 1)[0]]
            except KeyError:
                thing_type = '???'

            return '{0} ({1})'.format(thing.fullname, thing_type)
        return thing

    def send_debug_pm(self, subject, body, callback_depth=0):
        """
        Sends a pm to the AUTHOR reddit account
        """
        if self.__cfg.send_debug_pm:
            self.__error_handler.wait_for_rate_limit()

            if not (isinstance(body, basestring) and body):
                logger.prepend_id(logger.debug, self,
                        'Cannot send debug pm: need non-empty body text,'
                        ' not \'{body}\' ({body_type}).',
                        body=body,
                        body_type=type(body),
                )
                return

            try:
                maintainer = self.__maintainer
            except AttributeError:
                maintainer = self.redditor(AUTHOR)
                self.__maintainer = maintainer

            if not maintainer:
                return

            logger.prepend_id(logger.debug, self,
                    'Sending debug pm to \'{maintainer}\':'
                    '\n{sep}'
                    '\n{body}'
                    '\n{sep}',
                    sep=Reddit.LINE_SEP,
                    maintainer=maintainer.name,
                    body=body,
            )

            try:
                maintainer.message(subject, body)

            except Forbidden as e:
                # failed to log in? bot account suspended?
                logger.prepend_id(logger.error, self,
                        'Failed to send debug pm to \'{name}\'!', e,
                        name=maintainer.name,
                )

            except praw.exceptions.APIException as e:
                if e.error_type.lower() in ['no_user', 'user_doesnt_exist']:
                    # deleted, banned, or otherwise doesn't exist
                    # (is AUTHOR spelled correctly?)
                    logger.prepend_id(logger.debug, self,
                            'Could not send debug pm to \'{name}\':'
                            ' does not exist.',
                            name=maintainer.name,
                    )
                    # flag that we shouldn't try to send any more debug pms
                    self.__maintainer = None

                else:
                    self.__error_handler.handle(
                            err=e,
                            depth=callback_depth,
                            callback=self.send_debug_pm,
                            callback_kwargs={
                                'subject': subject,
                                'body': body,
                                'callback_depth': callback_depth+1,
                            },
                    )

    def do_reply(self, thing, body, callback_depth=0):
        """
        thing.reply(body) wrapper
        See: https://github.com/praw-dev/praw/blob/master/praw/models/reddit/mixins/replyable.py
        """
        success = False
        # TODO: do all thing.reply methods require a non-empty body?
        if not (isinstance(body, basestring) and body):
            logger.prepend_id(logger.debug, self,
                    'Cannot reply to {color_thing} with \'{body}\''
                    ' ({body_type}). Needs non-empty string!',
                    color_thing=display_fullname(thing),
                    body=body,
                    body_type=type(body),
            )

        else:
            self.__error_handler.wait_for_rate_limit()

            logger.prepend_id(logger.debug, self,
                    'Replying to {color_thing}:'
                    '\n{sep}'
                    '\n{body}'
                    '\n{sep}',
                    color_thing=display_fullname(thing),
                    sep=Reddit.LINE_SEP,
                    body=body,
            )

            try:
                thing.reply(body)

            except (AttributeError, TypeError) as e:
                logger.prepend_id(logger.error, self,
                        'Could not reply to {color_thing}:'
                        ' no \'reply\' method!', e,
                        color_thing=display_fullname(thing),
                )

            except Forbidden as e:
                # TODO? blacklist subreddit instead
                # -> probably means bot was banned from subreddit
                # (could also mean auth failed, maybe something else?)
                logger.prepend_id(logger.error, self,
                        'Failed to reply to {color_thing}!', e, True,
                        color_thing=display_fullname(thing),
                )

            except praw.exceptions.APIException as e:
                success = self.__error_handler.handle(
                        err=e,
                        depth=callback_depth,
                        callback=self.do_reply,
                        callback_kwargs={
                            'thing': thing,
                            'body': body,
                            'callback_depth': callback_depth+1,
                        },
                )

            else:
                success = True

        return success


__all__ = [
        'split_prefixed_name',
        'is_subreddit',
        'is_subreddit_prefix',
        'is_user',
        'is_user_prefix',
        'prefix_subreddit',
        'prefix_user',
        'prefix',
        'pack_subreddits',
        'unpack_subreddits',
        'Reddit',
]

