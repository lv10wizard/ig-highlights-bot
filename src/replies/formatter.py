import re

import inflect

from constants import (
        BLACKLIST_URL_FMT,
        CONTACT_URL,
        HELP_URL,
        REPO_URL,
        THING_ID_PLACEHOLDER,
)
from src import reddit
from src.instagram import Instagram
from src.util import (
        get_padding,
        logger,
)


class Formatter(object):
    """
    Comment reply text formatter
    """

    COMMENT_CHARACTER_LIMIT = 1e4
    # tag usernames in the bot's replies so we can parse them back out easily
    USER_TAG = '[](#ig@{user_raw})'
    HEADER_FMT = '{0}[@{{user}}]({{link}}) highlights:'.format(USER_TAG)
    FOOTER_FMT = (
            '---\n^I&#32;am&#32;a&#32;bot.'
            '&#32;Did&#32;I&#32;get&#32;something&#32;wrong?'
            '&#32;Downvote&#32;to&#32;delete.'
            '&#32;[[Contact]({contact_url})]'
            # '&#32;[[Source]({source_url})]'
            '&#32;[[Block]({blacklist_url})]'
            '&#32;[[FAQ]({help_url})]'
            # non-standard bot codeword to let other bots know that this comment
            # was posted by a bot (see: https://www.reddit.com/2r4qt8)
            '&#32;[](#bot)'
    )
    HIGHLIGHT_FMT = '[{i}]({link})'
    LINE_DELIM = '\n\n'

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
                    user_raw='({0})'.format(Instagram.USERNAME_PTN)
            )
            user_re = re.compile(pattern)
            Formatter.USER_TAG_REGEX = user_re

        return user_re.findall(body)

    def __init__(self, username):
        self.username = username

        if not Formatter._inflect:
            Formatter._inflect = inflect.engine()

    def __str__(self):
        return self.__class__.__name__

    def format(self, ig_list, thing):
        """
        Formats the data into one or more reddit comment reply strings

        Returns a list of tuple(str, list):
                1st element = reply body (<= COMMENT_CHARACTER_LIMIT)
                2nd element = list of ig_users included in the first element
                    (sublist of ig_list)
        """
        replies = []
        current_reply = []
        ig_users = []
        # wrap the string in a list so it is easier to work with
        FOOTER = [Formatter.FOOTER_FMT.format(
                contact_url=CONTACT_URL.replace(
                    THING_ID_PLACEHOLDER, reddit.display_id(thing)
                ),
                source_url=REPO_URL,
                blacklist_url=BLACKLIST_URL_FMT.format(
                    to=self.username,
                ),
                help_url=HELP_URL,
        )]

        for ig in ig_list:
            header = Formatter.HEADER_FMT.format(
                    user_raw=ig.user,
                    # escape markdown characters
                    # (eg. '_foo_' => italicized 'foo')
                    user=re.sub(r'(_)', r'\\\1', ig.user),
                    link=ig.url,
            )
            highlights = []
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

            current_reply.append(header)
            current_reply.append(' - '.join(highlights))
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
        # XXX: assumes each whole reply constitutes two elements
        step = 2
        full_reply = Formatter.LINE_DELIM.join(current_reply + footer)
        while len(full_reply) >= Formatter.COMMENT_CHARACTER_LIMIT:
            # the total size of the current reply exceeds the maximum allowed
            # comment character length

            # truncate individual ig_user highlights from the end of the reply
            # until the reply is under the character limit
            idx -= step
            full_reply = Formatter.LINE_DELIM.join(
                    current_reply[:idx] + footer
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

