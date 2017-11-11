import random

from src import reddit
from src.database import UserPoolDatabase
from src.instagram import Instagram
from src.mixins import (
        ProcessMixin,
        RedditInstanceMixin,
)
from src.util import logger


class Submitter(ProcessMixin, RedditInstanceMixin):
    """
    The bot's submitter process that posts submissions to its profile
    """

    def __init__(self, cfg, rate_limited):
        ProcessMixin.__init__(self)
        RedditInstanceMixin.__init__(self, cfg, rate_limited)

    def __str__(self):
        return self.__class__.__name__

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
            cut_off = int( 0.2 * len(ig.non_highlighted_media) )
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

    def _choose_ig_user(self):
        """
        Chooses a public instagram username from the user pool to post

        Returns the user's Instagram instance
        """
        # XXX: re-initialize the exclude set every pass in case any
        # previously excluded users changed eg. from private -> public
        # (this is very unlikely to ever happen)
        exclude = set()
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
                ig = Instagram(user)
                if ig.non_highlighted_media is None:
                    # fetch interrupted; retry when the delay is over
                    logger.id(logger.debug, self,
                            'Fetch interrupted:'
                            ' waiting {time} ({strftime}) ...',
                            time=Instagram.request_delay,
                            strftime='%H:%M:%S',
                            strf_time=Instagram.request_delay_expire,
                    )
                    ig = None
                    self._killed.wait(Instagram.request_delay)

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
                                ' Choosing another user ...',
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
        if link_pool:
            link = random.choice(link_pool)
        else:
            logger.id(logger.debug, self,
                    'Cannot choose link: no postable links to choose from!',
            )

        if link:
            logger.id(logger.debug, self,
                    'Selected \'{link}\' to post',
                    link=link,
            )

        return link

    def _format_title(self, ig):
        if ig.full_name:
            return '{0} (@{1})'.format(ig.full_name, ig.user)
        else:
            return '@{0}'.format(ig.user)

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

        while not self._killed.is_set():
            posted = False

            if self.cfg.submit_enabled:
                while posted is False:
                    ig = self._choose_ig_user()
                    if not ig:
                        logger.id(logger.info, self,
                                'Failed to choose an instagram user!',
                        )
                        break

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
                            with self.userpool:
                                self.userpool.commit_post(ig.username, link)

                            logger.id(logger.info, self,
                                    'Posting to {color_subreddit}:'
                                    ' \'{title}\' -> \'{link}\'',
                                    color_subreddit=reddit.prefix_subreddit(
                                        subreddit
                                    ),
                                    title=title,
                                    link=link,
                            )

                            posted = self._reddit.do_submit(
                                    display_name=subreddit,
                                    title=self._format_title(ig),
                                    url=link,
                            )
                            if posted is not None:
                                # submit either succeeded or was
                                # ratelimit-queued. commit it to the userpool
                                # so that the next post is not a duplicate.
                                # (this assumes that the ratelimit handler will
                                #  ultimately succeed in submitting the post.)
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

            if posted is None:
                logger.id(logger.info, self,
                        'Halting: could not post to {color_subreddit} ...',
                        color_subreddit=reddit.prefix_subreddit(subreddit),
                )
                break

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

