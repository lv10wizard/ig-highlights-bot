import multiprocessing
import os
import re
import sys
import time

import praw
from prawcore.exceptions import (
        Forbidden,
        OAuthException,
        RequestException,
)
from six import (
        iteritems,
        string_types,
)
from six.moves import input

import constants
from constants import (
        AUTHOR,
        PREFIX_SUBREDDIT,
        PREFIX_USER,
)
from src import (
        config,
        database,
)
from src.util import logger
from src.util.version import get_version


def split_prefixed_name(name):
    """
    Attempts to split the specified name into its prefix & name components
    eg. 'u/foobar' -> ('u/', 'foobar')

    Returns tuple (prefix, name) if successful
            tuple ('', name) if no prefix was found
    """
    REGEX = r'^/?({0}|{1})([\-\w]*)$'.format(PREFIX_USER, PREFIX_SUBREDDIT)
    #         | |\_______/\_______/|
    #         | |    |        |   don't include partial matches
    #         | |    |     capture user/subreddit name characters
    #         |  \  capture prefix
    #         | optionally match a leading '/' (eg. /r/test)
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
    return (
            prefix == PREFIX_SUBREDDIT
            or prefix == database.BlacklistDatabase.TYPE_SUBREDDIT
    )

def is_user(name):
    """
    Returns True if the prefix matches the user prefix (ie, 'u/')
    """
    prefix, name_raw = split_prefixed_name(name)
    return is_user_prefix(prefix)

def is_user_prefix(prefix):
    return (
            prefix == PREFIX_USER
            or prefix == database.BlacklistDatabase.TYPE_USER
    )

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
    if prefix == database.BlacklistDatabase.TYPE_USER:
        prefix = PREFIX_USER
    elif prefix == database.BlacklistDatabase.TYPE_SUBREDDIT:
        prefix = PREFIX_SUBREDDIT

    if re.search(r'^{0}'.format(prefix), name):
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

_NO_CALLBACK_RESULT = '!!!!!__CALLBACK__FAILED__!!!!!'
def _network_wrapper(callback, thing, *args, **kwargs):
    """
    Wraps the callback in a try/except against network issues
    """
    result = _NO_CALLBACK_RESULT
    delay = 1
    while result == _NO_CALLBACK_RESULT:
        try:
            result = callback(thing, *args, **kwargs)

        except RequestException:
            logger.id(logger.warn, thing.__repr__(),
                    'Failed to fetch {callback}; retrying in {time} ...',
                    callback=callback.__name__,
                    time=delay,
                    exc_info=True,
            )
            try:
                # try Event.wait so that we don't get stuck sleeping through
                # shutdown
                Reddit._killed.wait(delay)
            except AttributeError:
                time.sleep(delay)
            finally:
                try:
                    # test _killed in case it is a bool and not an Event
                    if isinstance(Reddit._killed, bool):
                        killed = Reddit._killed
                    else:
                        killed = Reddit._killed.is_set()
                except AttributeError:
                    pass
                else:
                    if killed:
                        break
            delay *= 2

    return result if result != _NO_CALLBACK_RESULT else None

def display_id(thing):
    def _display_id(thing):
        if hasattr(thing, 'permalink'):
            try:
                return thing.permalink()
            except TypeError:
                # object is not callable: thing should be a submission
                return thing.permalink

        return thing

    return _network_wrapper(_display_id, thing)

def display_fullname(thing):
    if hasattr(thing, 'fullname'):
        split = split_fullname(thing.fullname)
        try:
            thing_type = Reddit._kinds[split[0]]
        except KeyError:
            thing_type = '???'

        return '{0} ({1})'.format(thing.fullname, thing_type)
    return thing

def author(thing):
    def _author(thing):
        author = '[deleted/removed]'
        if hasattr(thing, 'author') and thing.author:
            author = thing.author.name
        return author

    return _network_wrapper(_author, thing)

def split_fullname(fullname):
    """
    Returns [type_str, id] from a {fullname} (eg. 't3_6zztml')
            or {fullname} if the string does not look like a proper fullname
    """
    if isinstance(fullname, string_types) and '_' in fullname:
        return fullname.split('_', 1)
    return fullname

def get_type_from_fullname(fullname):
    """
    Returns one of 'comment', 'message', 'subreddit', 'submission', 'redditor'
                based on the fullname

            or None if no type could be determined
    """
    result = None
    split = split_fullname(fullname)
    if isinstance(split, list):
        try:
            result = Reddit._kinds[split[0]]
        except KeyError:
            logger.id(logger.debug, split[0],
                    'Failed to determine type from fullname=\'{fullname}\'!',
                    fullname=fullname,
                    exc_info=True,
            )

    return result

def get_submission_for(thing):
    """
    Returns the praw.models.Submission for the give thing
            or None if the thing has no submission
    """
    def _get_submission_for(thing):
        if isinstance(thing, praw.models.Comment):
            return thing.submission
        elif isinstance(thing, praw.models.Submission):
            return thing

        return None

    return _network_wrapper(_get_submission_for, thing)

def get_ancestor_tree(comment, to_lower=True):
    """
    Returns a list of comments starting with the parent of the given
    comment, traversing up until the root comment is hit. That is, the list
    is ordered from parent [0] -> root [N-1]. In other words, a reversed
    comment tree.

    comment (praw.models.Comment) - the comment to get the ancestors of
    to_lower (bool, optional) - whether the list results should be lower-cased
    """
    # TODO? cache results for each comment-id hit to potentially lower
    # number of requests made (in the unlikely event that we need the
    # ancestors of a sibling this comment)

    # https://praw.readthedocs.io/en/latest/code_overview/models/comment.html#praw.models.Comment.parent
    def _get_ancestor_tree(comment, to_lower):
        result = []
        ancestor = comment
        refresh_counter = 0
        while not ancestor.is_root:
            ancestor = ancestor.parent()
            result.append(ancestor)
            if refresh_counter % 9 == 0:
                # TODO? catch praw.exceptions.ClientException:
                # This comment does not appear to be in the comment tree
                ancestor.refresh()
            refresh_counter += 1
        return result

    return _network_wrapper(_get_ancestor_tree, comment, to_lower)

# ######################################################################

class Reddit(praw.Reddit):
    """
    praw.Reddit wrapper
    """

    NOTSET_TYPE = praw.config._NotSet
    NOUSER_ERR = ('NO_USER', 'USER_DOESNT_EXIST')
    RATELIMIT_ERR = ('RATELIMIT',)

    LINE_SEP = '=' * 72

    _kinds = {}

    def __init__(self, cfg, rate_limited, *args, **kwargs):
        self.__cfg = cfg
        self.__rate_limit_queue = database.RedditRateLimitQueueDatabase()
        self.__rate_limited = rate_limited

        praw.Reddit.__init__(self,
                site_name=cfg.praw_sitename,
                user_agent=self.user_agent,
                *args, **kwargs
        )

        if not Reddit._kinds:
            Reddit._kinds = {
                    type_prefix: thing_name
                    for thing_name, type_prefix in
                    iteritems(self.config.kinds)
            }

        praw_ini_login = True
        manual_login = False
        # prevent other processes logging while trying to get user input
        with logger.lock():
            logger.id(logger.debug, self,
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

            logger.id(logger.exception, self,
                    ' '.join(msg),
                    username=self.username_raw or '<Not Set>',
                    section=cfg.praw_sitename,
            )
            raise

        logger.id(logger.debug, self,
                '\n\tclient id:  {client_id}'
                '\n\tuser name:  {username}'
                '\n\tuser agent: {user_agent}',
                client_id=self.config.client_id,
                username=self.username_raw,
                user_agent=self.user_agent,
        )

    def __str__(self):
        result = [self.__class__.__name__]
        if self.username:
            result.append(self.username)
        return ':'.join(result)

    @property
    def username_raw(self):
        raw = self.config.username
        return raw if not isinstance(raw, Reddit.NOTSET_TYPE) else None

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
            version = get_version()
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

    @property
    def is_rate_limited(self):
        return self.__rate_limited.is_set()

    def __try_set_username(self):
        """
        Asks the user to enter the bot account username if not defined in
        praw.ini
        """
        did_set = False
        if isinstance(self.config.username, Reddit.NOTSET_TYPE):
            self.config.username = input('bot account username: ')
            self.__warn_if_wrong_praw_version()
            self._prepare_prawcore()
            did_set = True
        return did_set

    def __try_set_password(self):
        """
        Asks the user to enter the bot account password if it was not defined
        in praw.ini
        """
        from getpass import getpass

        did_set = False
        while isinstance(self.config.password, Reddit.NOTSET_TYPE):
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
                logger.id(logger.warn, self,
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
            logger.id(logger.exception, self,
                    'Failed to determine praw version!',
            )
            raise
        else:
            if not (major == 5 and minor == 1 and revision == 0):
                logger.id(logger.warn, self,
                        'praw version != 5.1.0 (version={ver});'
                        ' authentication may fail!',
                        ver=praw.__version__,
                )

    def __handle_api_exception(self, err):
        """
        Generic APIException handling
        """
        if isinstance(err, praw.exceptions.APIException):
            if err.error_type.upper() in Reddit.RATELIMIT_ERR:
                self.__flag_rate_limit(err.message)

            else:
                logger.id(logger.debug, self, 'Ignoring ...', exc_info=True)

    def __flag_rate_limit(self, err_msg):
        """
        Flags that we are rate-limited by reddit
        """
        if not self.is_rate_limited:
            try:
                delay = config.parse_time(err_msg)
            except config.InvalidTime:
                delay = 10 * 60
                logger.id(logger.debug, self,
                        'Could not determine appropriate rate-limit delay:'
                        ' using {time}',
                        time=delay,
                )
            else:
                # fudge the ratelimit time a bit (the time given by reddit is
                # not precise)
                delay += 90

            self.__rate_limited.value = time.time() + delay
            logger.id(logger.info, self,
                    'Flagging rate-limit: \'{errmsg}\'',
                    errmsg=err_msg,
            )

        else:
            # another process hit the rate-limit (probably)
            delay = self.__rate_limited.remaining
            if delay > 0:
                logger.id(logger.debug, self,
                        'Attempted to flag rate-limit again: \'{errmsg}\''
                        ' (time left: {time} = {strftime})',
                        errmsg=err_msg,
                        time=delay,
                        strftime='%H:%M:%S',
                        strf_time=self.__rate_limited.value,
                )

            else:
                # this shouldn't happen
                logger.id(logger.warn, self,
                        'Invalid rate-limit time left ({time} = {strftime})!'
                        '\n(message: {errmsg})',
                        time=delay,
                        strftime='%H:%M:%S',
                        strf_time=self.__rate_limited.value,
                        errmsg=err_msg,
                )

    def __queue_reply(self, thing, body, force=False):
        """
        Enqueues the reply to {thing} (see: RateLimitHandler)

        thing (praw.models.*) - the {thing} to queue (should be Replyable)
        body (str) - the text to reply to {thing} with
        force (bool, optional) - whether the {thing} should be enqueued,
                ignoring current rate-limit status

        Returns True if queued successfully
                False if enqueue failed
                None if rate-limit is over
        """
        success = False
        delay = self.__rate_limited.remaining
        if delay > 0 or force:
            submission = get_submission_for(thing)
            logger.id(logger.info, self,
                    'Rate-limited! Queueing {color_thing}'
                    ' (expires @ {time} = {strftime}) ...',
                    color_thing=display_id(thing),
                    time=self.__rate_limited.remaining,
                    strftime='%H:%M:%S',
                    strf_time=self.__rate_limited.value,
            )

            try:
                with self.__rate_limit_queue:
                    self.__rate_limit_queue.insert(
                            thing, body, delay, submission,
                    )

            except database.UniqueConstraintFailed:
                # this may mean that the ratelimit handling is not timed
                # correctly or simply that the bot was ratelimited again
                logger.id(logger.debug, self,
                        'Updating {color_thing} in ratelimit queue ...',
                        color_thing=display_id(thing),
                )
                with self.__rate_limit_queue:
                    self.__rate_limit_queue.update(thing, body, delay)
            else:
                success = True

        else:
            # rate limit reset
            success = None

        return success

    def __dry_run_test(self):
        """
        "Randomly" chooses whether to throw an exception or do nothing if the
        bot is running as a dry_run
        """
        ran_test = False
        if constants.dry_run:
            try:
                self.__dry_run_test_number *= 2
            except AttributeError:
                self.__dry_run_test_number = 1
            num_call = self.__dry_run_test_number

            def raise_forbidden():
                import requests

                # fake a Forbidden response
                fake_response = requests.Response()
                fake_response.reason = 'DRY-RUN FORBIDDEN TEST'
                fake_response.status_code = 403
                logger.id(logger.info, self,
                        'Dry run: raising Forbidden: {reason} ...',
                        reason=fake_response.reason,
                )
                raise Forbidden(fake_response)

            # base decision off the number of times this method has been called
            if num_call == 1:
                raise_forbidden()
                ran_test = True

            else:
                import random

                # lower the chance of raising a ratelimit exception as the
                # number of calls increases (100% the first time)
                decision = random.randint(2, num_call)
                if decision == 2:
                    # throw a fake rate-limit exception
                    err_type = Reddit.RATELIMIT_ERR[0]
                    logger.id(logger.info, self,
                            'Dry run: raising {err_type} ...',
                            err_type=err_type,
                    )
                    err = [
                            err_type,

                            'you are doing that too much.'
                            ' try again in {0} minutes.'.format(
                                random.randint(1, 4)
                            ),

                            None,
                    ]
                    raise praw.exceptions.APIException(*err)
                    ran_test = True

                elif decision == 3:
                    raise_forbidden()
                    ran_test = True

        # pretty sure this isn't needed
        return ran_test

    def send_debug_pm(self, subject, body):
        """
        Sends a pm to the AUTHOR reddit account
        """
        if self.__cfg.send_debug_pm:
            if self.is_rate_limited:
                logger.id(logger.debug, self,
                        'Rate-limited! Skipping sending debug pm:'
                        ' \'{subject}\' (expires @ {time} = {strftime})',
                        subject=subject,
                        time=self.__rate_limited.remaining,
                        strftime='%H:%M:%S',
                        strf_time=self.__rate_limited.value,
                )
                return

            if not (isinstance(body, string_types) and body):
                logger.id(logger.debug, self,
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

            logger.id(logger.debug, self,
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
                logger.id(logger.exception, self,
                        'Failed to send debug pm to \'{author_name}\'!',
                        author_name=maintainer.name,
                )

            except praw.exceptions.APIException as e:
                if e.error_type.upper() in Reddit.NOUSER_ERR:
                    # deleted, banned, or otherwise doesn't exist
                    # (is AUTHOR spelled correctly?)
                    logger.id(logger.debug, self,
                            'Could not send debug pm to \'{author_name}\':'
                            ' does not exist.',
                            author_name=maintainer.name,
                    )
                    # flag that we shouldn't try to send any more debug pms
                    # Note: this is NOT persistent
                    self.__maintainer = None

                else:
                    self.__handle_api_exception(e)

    def do_reply(self, thing, body, killed=None):
        """
        thing.reply(body) wrapper
        See: https://github.com/praw-dev/praw/blob/master/praw/models/reddit/mixins/replyable.py

        killed (multiprocessing.Event, optional) - process loop condition used
                to gracefully exit from this method in case it gets stuck
                attempting to queue the reply from a rogue ratelimit.
        """
        success = False
        # TODO: do all thing.reply methods require a non-empty body?
        if not (isinstance(body, string_types) and body):
            logger.id(logger.debug, self,
                    'Cannot reply to {color_thing} with \'{body}\''
                    ' ({body_type}). Needs non-empty string!',
                    color_thing=display_id(thing),
                    body=body,
                    body_type=type(body),
            )

        else:
            # this is to prevent the queue while-loop from infinitely looping
            def was_killed(killed):
                return hasattr(killed, 'is_set') and killed.is_set()

            num_attempts = 0
            queued = None
            # XXX: try to queue in a loop in case the rate-limit ends while
            # attempting to queue the reply but starts again from a different
            # process
            while self.is_rate_limited and not was_killed(killed):
                # num_attempts should not grow > 2
                # 1  = rate-limited do_reply entry
                # 2  = was not rate-limited during __queue_reply but became
                #      rate-limited again
                # 3+ = ???
                num_attempts += 1
                if num_attempts > 1:
                    # very spammy if this somehow gets stuck looping
                    logger.id(logger.debug, self,
                            '[#{num}] Attempting to queue {color_thing}'
                            ' (rate-limited? {yesno_ratelimit};'
                            ' time left: {time} = {strftime})',
                            num=num_attempts,
                            color_thing=display_id(thing),
                            yesno_ratelimit=self.is_rate_limited,
                            time=self.__rate_limited.remaining,
                            strftime='%H:%M:%S',
                            strf_time=self.__rate_limited.value,
                    )

                queued = self.__queue_reply(thing, body)
                if queued is not None:
                    break

            if queued is None and not was_killed(killed):
                logger.id(logger.debug, self,
                        'Replying to {color_thing}:'
                        '\n{sep}'
                        '\n{body}'
                        '\n{sep}',
                        color_thing=display_id(thing),
                        sep=Reddit.LINE_SEP,
                        body=body,
                )

                try:
                    if not constants.dry_run:
                        thing.reply(body)
                    else:
                        if not self.__dry_run_test():
                            logger.id(logger.info, self,
                                    'Dry run: skipping reply to {color_thing}',
                                    color_thing=display_id(thing),
                            )

                except (AttributeError, TypeError) as e:
                    logger.id(logger.warn, self,
                            'Could not reply to {color_thing}:'
                            ' no \'reply\' method!',
                            color_thing=display_id(thing),
                            exc_info=True,
                    )

                except Forbidden as e:
                    # TODO? blacklist subreddit / user instead (base off thing
                    # type)
                    # - probably means bot was banned from subreddit
                    #   or blocked by user
                    # (could also mean auth failed, maybe something else?)
                    logger.id(logger.warn, self,
                            'Failed to reply to {color_thing}!',
                            color_thing=display_id(thing),
                            exc_info=True,
                    )

                except praw.exceptions.APIException as e:
                    self.__handle_api_exception(e)

                    if e.error_type.upper() in Reddit.RATELIMIT_ERR:
                        # force in case the rate-limit flag is unset somehow
                        self.__queue_reply(thing, body, force=True)

                else:
                    success = True

        return success

    def get_thing_from_fullname(self, fullname):
        """
        Returns a praw.models.* object constructed from its fullname
                eg. 't1_foobar' -> praw.models.Comment(id='foobar')
        """
        thing = None
        thing_name = get_type_from_fullname(fullname)
        if thing_name:
            thing_prefix, thing_id = split_fullname(fullname)

            try:
                if hasattr(self, thing_name):
                    # comment, submission, subreddit, redditor
                    thing_class = getattr(self, thing_name)
                    thing = thing_class(thing_id)

                    # XXX: this doesn't work for subreddits and redditors since
                    # the reddit object expects the display name to construct
                    # these objects
                    if (
                            isinstance(thing, praw.models.Subreddit)
                            or isinstance(thing, praw.models.Redditor)
                    ):
                        logger.id(logger.debug, self,
                                'Unhandled type: {color_name}'
                                ' ({color_fullname})',
                                color_name=thing_name,
                                color_fullname=fullname,
                        )
                        thing = None

                elif hasattr(praw.models, thing_name.capitalize()):
                    # message
                    # XXX: this object is woefully incomplete; it does not have
                    # eg. 'body', 'author', etc
                    thing_class = getattr(praw.models, thing_name.capitalize())
                    thing = thing_class(self, None)
                    thing.id = thing_id

                else:
                    logger.id(logger.debug, self,
                            'Unknown thing type: \'{color_name}\''
                            ' ({color_fullname})',
                            color_name=thing_name,
                            color_fullname=fullname,
                    )

            except AttributeError:
                # this shouldn't happen
                logger.id(logger.exception, self,
                        'Failed to construct {color_name} from'
                        ' fullname=\'{color_fullname}\'!',
                        color_name=thing_name,
                        color_fullname=fullname,
                )

        else:
            logger.id(logger.debug, self,
                    'Unrecognized fullname=\'{color_fullname}\'',
                    color_fullname=fullname,
            )

        return thing


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
        'display_id',
        'display_fullname',
        'author',
        'split_fullname',
        'get_type_from_fullname',
        'get_submission_for',
        'get_ancestor_tree',
        'Reddit',
]

