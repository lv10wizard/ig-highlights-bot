from getpass import getpass
import re
import sys
import time
from urlparse import urlparse

import praw
from prawcore.exceptions import (
        Forbidden,
        Redirect,
)
from utillib import (
        logger,
        soup,
)

from src import (
        config,
        comments,
        database,
        instagram,
        mentions,
        messages,
)


class IgHighlightsBot(object):
    """
    """

    WANT_MORE = 'More'

    # TODO: move to config
    ME = 'ig-highlights-bot'
    AUTHOR = '/u/lv10wizard'
    SITENAME_PATH = os.path.join(
            os.path.dirname(
                os.path.realpath(os.path.abspath(__file__))
            ),
            # XXX: assumes the this file is one directory below where the
            # SITENAME file lives
            '..',
            'SITENAME',
    )

    def __init__(self):
        # self.config = config.Config()
        self.reply_history = database.ReplyDatabase()
        # self.messages = messages.Messages()
        # self.mentions = mentions.Mentions()

        self._reddit = praw.Reddit(
                site_name=self.site_name,
                user_agent=self.user_agent,
        )
        self.try_set_password()

        logger.prepend_id(logger.debug, self,
                'client id: {client_id}'
                '\nuser name: {username}'
                '\nuser agent: {user_agent}',
                client_id=self._reddit.config.client_id,
                username=self.username_raw,
                user_agent=self.user_agent,
        )

    def __str__(self):
        return self.username_raw

    def try_set_password(self):
        """
        Asks the user to enter the bot account password if it was not defined
        in praw.ini
        """
        while isinstance(self._reddit.config.password, praw.config._NotSet):
            first = getpass('{0} password: '.format(self.username))
            second = getpass('Re-enter password: ')
            if first == second:
                self._reddit.config.password = first

                # https://github.com/praw-dev/praw/blob/master/praw/reddit.py
                # XXX: praw's Config.password is just a member variable; setting
                # it does not actually allow authentication if the password
                # is set after Reddit.__init__
                self.warn_if_wrong_praw_version()
                # the following call works as of praw 5.1 (may break in later
                # versions)
                self._reddit._prepare_prawcore()
            else:
                logger.prepend_id(logger.warn, self,
                        'Passwords do not match! Please try again.',
                )

    def warn_if_wrong_praw_version(self):
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

    @property
    def site_name(self):
        # TODO: move to config
        result = ME
        try:
            with open(IgHighlightsBot.SITENAME_PATH, 'rb') as fd:
                sitename = fd.read()
        except (IOError, OSError) as e:
            logger.prepend_id(logger.info, self,
                    'Failed to read sitename: defaulting to {result}',
                    result=result,
            )
        else:
            if not sitename:
                logger.prepend_id(logger.info, self,
                        'Invalid sitename=\'{sitename}\';'
                        ' defaulting to {result}',
                        sitename=sitename,
                        result=result,
                )
            else:
                result = sitename
        return result

    @property
    def username_raw(self):
        """
        """
        return self._reddit.config.username

    @property
    def username(self):
        """
        """
        return '/u/{0}'.format(self.username_raw)

    @property
    def user_agent(self):
        """
        """
        try:
            user_agent = self.__user_agent
        except AttributeError:
            version = '0.1' # TODO: read from file
            self.__user_agent = (
                    '{platform}:{appname}:{version} (by {author})'
            ).format(
                    platform=sys.platform,
                    appname=IgHighlightsBot.ME,
                    version=version,
                    author=IgHighlightsBot.AUTHOR,
            )
            user_agent = self.__user_agent
        return user_agent

    def _format_reply(self, comment, ig):
        more = ' ^^Reply ^^`{more}` ^^for ^^more ^^highlights'.format(
                more=IgHighlightsBot.WANT_MORE,
        )
        header = '### [{user}]({link}) highlights:'.format(
                user=ig.user,
                link=ig.link,
        )
        # only allow more to be posted once per comment chain
        if False: # TODO
            header += more
        footer = (
                '\n---\n^Beep ^Boop. ^I ^am ^definitely ^human.'
                ' ^[[Contact]({contact_url})]'
                # ' ^[[Source]({source_url})]'
        ).format(
                contact_url= >> TODO <<,
                # source_url= >> TODO <<,
        )

    def reply(self, comment, ig, is_callback=False):
        """
        """
        logger.prepend_id(logger.debug, self,
                '',
        )
        ig = instagram.Instagram(link)
        if ig.valid:
            try:
                # TODO: comment.reply(...); history.add(comment.id, ig.user)
                pass

            except Forbidden as e:
                logger.prepend_id(logger.error, self,
                        'Failed to reply to comment {color_sub}/{color_id}!',
                        e, True,
                        color_sub=comment.subreddit_name_prefixed,
                        color_id=comment.id,
                )

            except praw.exceptions.APIException as e:
                if is_callback:
                    # this is the second (or more) time that reply has failed;
                    # something is probably wrong
                    raise

                self._handle_rate_limit(
                        err=e,
                        callback=self.reply,
                        callback_kwargs={
                            'comment': comment,
                            'ig': ig,
                            'is_callback': True,
                        },
                )

    def _handle_rate_limit(self, err, callback, callback_args=(),
            callback_kwargs={},
    ):
        """
        """
        if (
                hasattr(err, 'error_type')
                and isinstance(err.error_type, str)
                and re.search(r'ratelimit', err.error_type.lower())
        ):
            delay = 10

            try:
            except (TypeError, ValueError):
                pass

            delay *= 60
            logger.prepend_id(logger.error, self,
                    'Rate limited! Trying again in {time} ...', err,
                    time=delay,
            )
            time.sleep(delay)
            callback(*callback_args, **callback_kwargs)

        else:
            raise

    def run_forever(self):
        """
        """
        # TODO: start inbox message forwarding process
        # TODO: start mentions parser process
        # TODO: start comment replies process
        subs = self._reddit.subreddit(self.subs)
        try:
            for comment in subs.stream.comments(pause_after=0):
                pass # TODO: if is_valid_link(c) => reply

        except Redirect as e:
            if re.search(r'/subreddits/search', e.message):
                logger.prepend_id(logger.error, self,
                        'One or more non-existent subreddits:'
                        ' {unpack_color}', e,
                        unpack_color=subs.split('+'),
                )


__all__ = [
        'IgHighlightsBot',
]

