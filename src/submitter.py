import os
import random
import time

import constants
from src import reddit
from src.database import (
        Database,
        UserPoolDatabase,
)
from src.instagram import (
        Fetcher,
        Instagram,
)
from src.mixins import (
        ProcessMixin,
        RedditInstanceMixin,
)
from src.util import (
        logger,
        readline,
)


class Submitter(ProcessMixin, RedditInstanceMixin):
    """
    The bot's submitter process that posts submissions to its profile
    """

    _LAST_POST_TIME_FILE = Database.resolve_path(
            Database.format_path('submitter_last_post_time')
    )

    _NOT_SET = '__:!NOT!SET!:__'

    @staticmethod
    def _load_last_post_time():
        """
        Loads the last post time from file

        Returns the timestamp of the last post time
                or -1 if the _LAST_POST_TIME_FILE could not be read
        """
        last_post_time = -1
        if os.path.exists(Submitter._LAST_POST_TIME_FILE):
            logger.id(logger.debug, __name__,
                    'Loading last post time from \'{path}\' ...',
                    path=Submitter._LAST_POST_TIME_FILE,
            )

            for i, line in readline(Submitter._LAST_POST_TIME_FILE):
                try:
                    last_post_time = float(line)

                except (TypeError, ValueError):
                    # file structure changed or corrupted
                    logger.id(logger.warn, Submitter._LAST_POST_TIME_FILE,
                            'Invalid last post time data: \'{data}\'',
                            data=line,
                            exc_info=True,
                    )

                finally:
                    # break in case there are too many lines
                    break

            if last_post_time > 0:
                logger.id(logger.debug, __name__,
                        'Loaded last post time from file: {strftime}',
                        strftime='%m/%d, %H:%M:%S',
                        strf_time=last_post_time,
                )

            else:
                Submitter._remove_last_post_time_file()

        return last_post_time

    @staticmethod
    def _record_last_post_time():
        """
        Writes the current time to the _LAST_POST_TIME_FILE
        """
        logger.id(logger.debug, __name__,
                'Writing last post time: {strftime} ...',
                strftime='%m/%d, %H:%M:%S',
        )

        try:
            with open(Submitter._LAST_POST_TIME_FILE, 'w') as fd:
                fd.write(str(time.time()))

        except (IOError, OSError):
            logger.id(logger.exception, __name__,
                    'Failed to record last post time: {strftime}',
                    strftime='%m/%d, %H:%M:%S',
            )

    @staticmethod
    def _remove_last_post_time_file():
        """
        Removes the _LAST_POST_TIME_FILE if it exists
        """
        if os.path.exists(Submitter._LAST_POST_TIME_FILE):
            logger.id(logger.debug, __name__,
                    'Removing last post time file \'{path}\' ...',
                    path=Submitter._LAST_POST_TIME_FILE,
            )

            try:
                os.remove(Submitter._LAST_POST_TIME_FILE)

            except (IOError, OSError):
                logger.id(logger.warn, __name__,
                        'Failed to remove \'{path}\'!',
                        path=Submitter._LAST_POST_TIME_FILE,
                        exc_info=True,
                )

    def __init__(self, cfg, rate_limited):
        ProcessMixin.__init__(self)
        RedditInstanceMixin.__init__(self, cfg, rate_limited)

    @property
    def userpool(self):
        try:
            userpool = self.__userpool
        except AttributeError:
            userpool = UserPoolDatabase(self.cfg)
            self.__userpool = userpool

        return userpool

    def _get_link_pool(self, ig, exclude=[]):
        """
        Returns a list of postable links for the given instagram user
        """
        pool = None
        try:
            # limit the pool to the top N% of the non-highlighted media
            cut_off = int( 0.1 * len(ig.non_highlighted_media) )
        except (AttributeError, TypeError):
            pool = []
        else:
            # XXX: this will break if the .non_highlighted_media link
            # format changes (ie, if the link format no longer matches
            # the links contained in exclude)
            pool = [
                    link for link in ig.non_highlighted_media[:cut_off]
                    if link not in exclude
            ]

        return pool

    def _wait_for_fetch_delay(self):
        """
        Attempts to wait out the remaining instagram fetch delay

        Returns True if a wait occurred
        """
        did_wait = False

        delay = Instagram.request_delay or Instagram.ratelimit_delay
        if delay > 0:
            expire = (
                    Instagram.request_delay_expire
                    or Instagram.ratelimit_delay_expire
            )

            msg = ['Fetch interrupted: waiting {time}']
            if expire > 0:
                msg.append('({strftime})')

            logger.id(logger.debug, self,
                    ' '.join(msg),
                    time=delay,
                    strftime='%H:%M:%S',
                    strf_time=expire,
            )
            self._killed.wait(delay)
            did_wait = True

        return did_wait

    def _choose_ig_user(self, exclude=set()):
        """
        Chooses a public instagram username from the user pool to post

        Returns the user's Instagram instance
        """
        ig = None
        while (
                not (ig or self._killed.is_set())
                # XXX: if the userpool changes during the loop then this
                # check may not accurately reflect the entire userpool being
                # ineligible to post. it should however still however function
                # properly in terms of preventing an infinite loop.
                or len(exclude) >= self.userpool.size()
        ):
            user = self.userpool.choose_username(exclude)
            # verify that the user's profile is still public
            while not (ig or self._killed.is_set()):
                ig = Instagram(user, self._killed)
                    logger.id(logger.debug, self,
                    )
                if ig.non_highlighted_media is None:
                    # fetch interrupted; retry when the delay is over
                    self._wait_for_fetch_delay()
                    ig = None

                elif (
                        ig.non_highlighted_media is True
                        or ig.non_highlighted_media is False
                ):
                    # private user or bad username
                    logger.id(logger.debug, self,
                            '{color_user} has no postable media:'
                            ' choosing another user ...',
                            color_user=user,
                    )
                    exclude.add(user)
                    ig = None
                    break

                elif ig.non_highlighted_media:
                    unique_count = self.cfg.submit_unique_links_per_user
                    link_pool = self._get_link_pool(ig)
                    if len(link_pool) <= unique_count:
                        # the user does not have enough posts for the bot to
                        # submit non-duplicate links -- choose another user
                        logger.id(logger.debug, self,
                                '{color_user} does not have enough posts'
                                ' (> #{unique_count} required).'
                                '\n\ttotal:           #{total}'
                                '\n\tnon-highlighted: #{non_highlighted}'
                                '\n\tpostable-links:  #{postable_links}'
                                '\nChoosing another user ...',
                                color_user=user,
                                unique_count=unique_count,
                                total=(
                                    len(ig.top_media)
                                    + len(ig.non_highlighted_media)
                                ),
                                non_highlighted=len(ig.non_highlighted_media),
                                postable_links=len(link_pool),
                        )
                        exclude.add(user)
                        ig = None
                        break

        if ig:
            logger.id(logger.debug, self,
                    'Selected {color_user} to post',
                    color_user=ig.user,
            )

        if len(exclude) >= self.userpool.size():
            # either the pool is too small or the config settings are too strict
            logger.id(logger.debug, self,
                    'Could not choose a user: entire pool is ineligible!',
            )

        return ig

    def _choose_post_link(self, ig):
        """
        Choose a link to post for the given user that is:
            1) not in the user's highlight set
            2) hasn't been posted recently

        Returns the link to post
                or None if something goes wrong
        """

        if not (ig or ig.non_highlighted_media):
            return

        link = None
        link_pool = self._get_link_pool(ig, self.userpool.last_posts(ig.user))
        while link_pool and not link:
            link = random.choice(link_pool)

            if link:
                # test the link to ensure it still exists
                response = None
                # XXX: don't test 'not response' because "bad" status codes
                # evaluate to False (eg. 404)
                while response is None or response is False:
                    response = Fetcher.request(link, method='head')
                    if response is False:
                        self._wait_for_fetch_delay()

                if (
                        hasattr(response, 'status_code')
                        and response.status_code == 404
                ):
                    logger.id(logger.debug, self,
                            '\'{url}\' no longer exists!'
                            ' Choosing another link ...',
                            url=link,
                    )

                    try:
                        link_pool.remove(link)
                    except ValueError:
                        # this should not happen
                        logger.id(logger.warn, self,
                                'Failed to remove 404\'d link \'{url}\''
                                ' from {color_user}\'s link_pool!',
                                url=link,
                                color_user=ig.user,
                                exc_info=True,
                        )
                    finally:
                        # choose another link
                        link = None

            else:
                # this shouldn't happen
                logger.id(logger.debug, self,
                        'Failed to choose a link from: {pprint_pool}',
                        pprint_pool=link_pool,
                )
                break

        if not link_pool:
            # user either deleted all/most of their posts or went private
            # or deleted their account/account shutdown
            logger.id(logger.debug, self,
                    'Cannot choose link:'
                    ' {color_user} has no postable links to choose from!',
                    color_user=ig.user,
            )

        if link:
            logger.id(logger.debug, self,
                    'Selected \'{link}\' to post',
                    link=link,
            )

        else:
            logger.id(logger.debug, self,
                    'Failed to select a link for {color_user}!',
                    color_user=ig.user,
            )

        return link

    def _format_title(self, ig):
        if ig.full_name:
            return '{0} (@{1})'.format(ig.full_name, ig.user)
        else:
            return '@{0}'.format(ig.user)

    def _submit_post(self, display_name, exclude=set()):
        """
        Submits a post to the bot's profile

        Returns the return value of do_submit if a post is attempted
                or _NOT_SET otherwise
        """
        posted = Submitter._NOT_SET
        ig = self._choose_ig_user(exclude)
        if not ig:
            logger.id(logger.info, self,
                    'Failed to choose an instagram user!',
            )
            # XXX: return False so that the run_forever loop does not exit
            # -- failing to choose an instagram user is not necessarily fatal,
            # it means that no username in the pool is currently valid to post
            # but may become valid in the future.
            return False

        if (
                not self._killed.is_set()
                and ig
                and hasattr(ig.non_highlighted_media, '__iter__')
        ):
            # choose a non-highlighted link to post
            link = self._choose_post_link(ig)
            if link:
                # commit the post before posting just in case
                # something goes wrong (to prevent the bot from
                # re-posting a duplicate)
                logger.id(logger.debug, self,
                        'Committing {color_user}:'
                        ' \'{color_link}\' to userpool to'
                        ' prevent reposting duplicates too'
                        ' quickly',
                        color_user=ig.user,
                        color_link=link,
                )
                with self.userpool:
                    self.userpool.commit_post(ig.user, link)

                title = self._format_title(ig)
                logger.id(logger.info, self,
                        'Posting to {color_subreddit}:'
                        ' \'{title}\' -> \'{link}\'',
                        color_subreddit=reddit.prefix_subreddit(display_name),
                        title=title,
                        link=link,
                )

                posted = self._reddit.do_submit(
                        display_name=display_name,
                        title=title,
                        url=link,
                )

            else:
                # don't re-select this user to post since it is unlikely
                # that they will gain any postable links
                logger.id(logger.debug, self,
                        'Excluding {color_user}: no postable links!',
                        color_user=ig.user,
                )
                exclude.add(ig.user)

        return posted

    def _run_forever(self):
        # XXX: this is not a config option because the bot should not post
        # to any random subreddit
        subreddit = None
        if self._reddit.profile_sub_name:
            subreddit = self._reddit.profile_sub_name

        if not subreddit:
            logger.id(logger.info, self,
                    'No subreddit to submit posts to'
                    ' (username invalid: \'{username}\')',
                    username=self._reddit.username_raw,
            )
            return

        else:
            logger.id(logger.info, self,
                    'Submitting posts to {color_subreddit} ...',
                    color_subreddit=reddit.prefix_subreddit(subreddit),
            )

        # check if the bot needs to wait before posting initially
        # (in case eg. it was restarted)
        last_post_time = Submitter._load_last_post_time()
        elapsed = time.time() - last_post_time
        delay = self.cfg.submit_interval - elapsed
        if delay > 0:
            logger.id(logger.info, self,
                    'Waiting {time} before posting ...',
                    time=delay,
            )
            self._killed.wait(delay)

        while not self._killed.is_set():
            posted = Submitter._NOT_SET

            if self.cfg.submit_enabled:
                # XXX: re-initialize the exclude set every pass in the unlikely
                # case where a previously excluded user changed
                # eg. from private -> public
                exclude = set()

                while (
                        not self._killed.is_set()
                        and posted is Submitter._NOT_SET
                ):
                    posted = self._submit_post(subreddit, exclude)

            if posted is None:
                logger.id(logger.info, self,
                        'Halting: could not post to {color_subreddit} ...',
                        color_subreddit=reddit.prefix_subreddit(subreddit),
                )

                Submitter._remove_last_post_time_file()

                if not constants.dry_run:
                    break

                else:
                    logger.id(logger.info, self, 'Dry run: not halting ...')

            else:
                Submitter._record_last_post_time()

            logger.id(logger.info, self,
                    'Waiting {time} before posting again ...',
                    time=self.cfg.submit_interval,
            )

            self._killed.wait(self.cfg.submit_interval)

        if self._killed.is_set():
            logger.id(logger.debug, self, 'Killed!')


__all__ = [
        'Submitter',
]

