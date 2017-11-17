import re

import inflect
from six import iteritems

from constants import (
        BLACKLIST_URL_FMT,
        CONTACT_URL,
        HELP_URL,
        REPO_URL,
        THING_ID_PLACEHOLDER,
)
from src import reddit
from src import instagram
from src.util import (
        get_padding,
        logger,
)


class Formatter(object):
    """
    Comment reply text formatter
    """

    NUM_PREFIX = {
            3: 'k',
            6: 'm',
            9: 'b',
            12: 't',
    }

    COMMENT_CHARACTER_LIMIT = 1e4

    SPACE = '&#32;'
    # tag usernames in the bot's replies so we can parse them back out easily
    USER_TAG = '[](#ig@{user_raw})'
    HEADER_HIGHLIGHTS = 'highlights:'
    HEADER_PRIVATE = '(private account)'
    HEADER_FMT = '{0}[@{{user}}]({{link}}) {{suffix}}'.format(USER_TAG)
    FOOTER_FMT = (
            '---\n^I am a bot.'
            ' Did I get something wrong?'
            ' Downvote to delete.'
            ' [[Contact]({contact_url})]'
            ' [[Block]({blacklist_url})]'
            # ' [[Source]({source_url})]'
            ' [[FAQ]({help_url})]'
            # non-standard bot codeword to let other bots know that this comment
            # was posted by a bot (see: https://www.reddit.com/2r4qt8)
            ' [](#bot)'.replace(' ', SPACE)
    )
    HIGHLIGHT_FMT = '[{i}]({link})'
    METADATA_FMT = '^[ {data} ]'.replace(' ', SPACE)
    LINE_DELIM = '\n\n'

    USER_SEPARATOR = '\n\n&nbsp;\n\n'

    _inflect = None

    @staticmethod
    def ig_users_in(body):
        """
        Returns a list of instagram usernames present in a reply body
                (if there are no usernames found, returns an empty list)
        """
        import re

        try:
            user_re = Formatter.USER_TAG_REGEX
        except AttributeError:
            # escape special characters so we can format the user-tag into a
            # regex pattern
            escaped_user_tag = re.sub(
                    # match any '[', ']', '(', or ')'
                    r'([\[\]\(\)])',
                    # escape the matched character
                    r'\\\1',
                    Formatter.USER_TAG
            )
            pattern = escaped_user_tag.format(
                    user_raw='({0})'.format(instagram.USERNAME_PTN)
            )
            user_re = re.compile(pattern)
            Formatter.USER_TAG_REGEX = user_re

        return user_re.findall(body)

    @staticmethod
    def format_large_number(num):
        """
        Returns a human-readable number of followers similar to instagram's
        implementation

        eg. 1234      -> '1,234'
            567892    -> '567.9k'
            2093321   -> '2.1m'
        """
        if num < 1e4: # 10,000
            # https://stackoverflow.com/a/10742904
            return '{:,}'.format(num)

        for exp, prefix in iteritems(Formatter.NUM_PREFIX):
            fraction = float(num) / float(10**exp)
            if 1 <= fraction < 1e3:
                return '{0:.1f}{1}'.format(fraction, prefix)

        # fallback to the highest defined defined prefix
        highest = max(Formatter.NUM_PREFIX)
        # comma separated in case there are more than 1,000 digits
        return '{0:,.1f}{1}'.format(
                float(num) / float(10**highest),
                Formatter.NUM_PREFIX[highest],
        )

    @staticmethod
    def format_url(url):
        """
        Returns a condensed markdown url
        """
        no_scheme = url.split('://', 1)[-1]
        return '[{0}]({1})'.format(no_scheme, url)

    def __init__(self, username):
        self.username = username

        if not Formatter._inflect:
            Formatter._inflect = inflect.engine()

    def __str__(self):
        return self.__class__.__name__

    def format(self, ig_list, thing, from_link, is_guess):
        """
        Formats the data into one or more reddit comment reply strings

        Returns a list of tuple(str, list):
                1st element = reply body (<= COMMENT_CHARACTER_LIMIT)
                2nd element = list of ig_users included in the first element
                    (sublist of ig_list)

                or an empty list if no reply should be made
        """
        replies = []
        current_reply = []
        ig_users = []
        FOOTER = Formatter.FOOTER_FMT.format(
                contact_url=CONTACT_URL.replace(
                    THING_ID_PLACEHOLDER, reddit.display_id(thing)
                ),
                source_url=REPO_URL,
                blacklist_url=BLACKLIST_URL_FMT.format(
                    to=self.username,
                ),
                help_url=HELP_URL,
        )

        for ig in ig_list:
            if ig.is_private and (from_link or is_guess):
                # don't link private profiles if there was already a link or
                # if the parser guessed the username (in case it guessed wrong)
                # -- the bot re-linking a private profile provides no real value
                #    and linking a guessed username that is private would
                #    dramatically increase the number of false positives
                logger.id(logger.info, self,
                        'Skipping {color_user}: {verb} private profile',
                        color_user=ig.user,
                        verb=('linked' if from_link else 'guessed'),
                )
                continue

            user_reply = []
            header = Formatter.HEADER_FMT.format(
                    user_raw=ig.user,
                    # escape markdown characters
                    # (eg. '_foo_' => italicized 'foo')
                    user=re.sub(r'(_)', r'\\\1', ig.user),
                    link=ig.url,
                    suffix=(
                        Formatter.HEADER_HIGHLIGHTS
                        if not ig.is_private
                        else Formatter.HEADER_PRIVATE
                    ),
            )

            highlights = []
            if not ig.private:
                media = ig.top_media
                for i, media_link in enumerate(media):
                    logger.id(logger.debug, self,
                            '[{i:>{pad}}/{num}] {color_user}: {link}',
                            i=i+1,
                            pad=get_padding(len(media)),
                            num=len(media),
                            color_user=ig.user,
                            link=media_link,
                    )
                    highlights.append(Formatter.HIGHLIGHT_FMT.format(
                        i=Formatter._inflect.number_to_words(i+1),
                        link=media_link,
                    ))

            metadata = []
            if ig.num_posts is not None and ig.num_posts >= 0:
                posts = '{0} posts'.format(
                        Formatter.format_large_number(ig.num_posts)
                )
                metadata.append(posts)
            if ig.num_followers is not None and ig.num_followers >= 0:
                followers = '~{0} followers'.format(
                        Formatter.format_large_number(ig.num_followers)
                )
                metadata.append(followers)
            if ig.private and ig.external_url:
                # external_urls are typically sponsored/donation links.
                # private accounts don't typically specify links but if they
                # do, there is a chance that it is useful.
                metadata.append(Formatter.format_url(ig.external_url))

            user_reply.append(header)
            user_reply.append(' - '.join(highlights))
            if metadata:
                # only format in metadata if we were able to fetch it
                # (this shouldn't happen)
                user_reply.append(Formatter.METADATA_FMT.format(
                    data=' | '.join(metadata).replace(' ', Formatter.SPACE)
                ))
            else:
                logger.id(logger.warn, self,
                        'Failed to get metadata for {color_user}!',
                        color_user=ig.user,
                )

            user_reply = list(filter(None, user_reply))
            current_reply.append(Formatter.LINE_DELIM.join(user_reply))
            ig_users.append(ig)

            # try to add the current reply if its character length exceeds
            # the limit
            current_reply, ig_users = self.__try_add_reply(
                    replies,
                    current_reply,
                    ig_users,
                    FOOTER,
            )

        # add the final reply to the replies list
        current_reply, ig_users = self.__try_add_reply(
                replies,
                current_reply,
                ig_users,
                FOOTER,
                force=bool(current_reply and ig_users),
        )
        if current_reply or ig_users:
            logger.id(logger.debug, self,
                    'Extra reply data not added!'
                    '\n\tcurrent_reply: {current_reply}'
                    '\n\tig_uesrs:      {ig_users}',
                    current_reply=current_reply,
                    ig_users=ig_users,
            )

        return replies

    def __try_add_reply(
            self, replies, current_reply, ig_users, footer, force=False
    ):
        """
        "Commits" the constructed reply text if the current_reply exceeds the
        COMMENT_CHARACTER_LIMIT.

        Returns (list, list):
                1st element = the remaining current_reply data that caused the
                    overflow
                2nd element = the overflow ig_users

        Returns (current_reply, ig_users) if the reply was not added
        """
        idx = 0
        # the number of elements in current_reply that constitutes a reply
        # for a single user
        step = 1
        full_reply = (
                Formatter.USER_SEPARATOR.join(filter(None, current_reply))
                + Formatter.LINE_DELIM + footer
        )
        while len(full_reply) >= Formatter.COMMENT_CHARACTER_LIMIT:
            # the total size of the current reply exceeds the maximum allowed
            # comment character length

            # truncate individual ig_user highlights from the end of the reply
            # until the reply is under the character limit
            idx -= step
            full_reply = (
                    Formatter.USER_SEPARATOR.join(
                        filter(None, current_reply[:idx])
                    ) + Formatter.LINE_DELIM + footer
            )

        # don't de-sync the reply & ig_users list in case an overflow happens
        # when force==True (if this happens, the overflow will be dropped)
        # -- basically: don't call this function with force==True if there may
        # be overflow
        if force and idx == 0:
            # set the idx so that all of current_reply and ig_users is used
            idx = len(current_reply)

        if idx != 0:
            ig_idx = idx // step
            replies.append( (full_reply, ig_users[:ig_idx]) )
            # return the remainder
            # if force: ([], [])
            current_reply = current_reply[idx:]
            ig_users = ig_users[ig_idx:]

        return current_reply, ig_users

__all__ = [
        'Formatter',
]

