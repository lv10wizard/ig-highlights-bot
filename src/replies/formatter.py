from constants import (
        BLACKLIST_URL_FMT,
        CONTACT_URL,
        HELP_URL,
        REPO_URL,
)
from src.util import (
        get_padding,
        logger,
)


class Formatter(object):
    """
    Comment reply text formatter
    """

    COMMENT_CHARACTER_LIMIT = 1e4
    HEADER_FMT = '[@{user}]({link}) highlights:'
    FOOTER_FMT = (
            '---\n^I&#32;am&#32;a&#32;bot.'
            '&#32;Did&#32;I&#32;get&#32;something&#32;wrong?'
            '&#32;Downvote&#32;to&#32;delete.'
            '&#32;[[Contact]({contact_url})]'
            '&#32;[[Source]({source_url})]'
            '&#32;[[Block]({blacklist_url})]'
            '&#32;[[FAQ]({help_url})]'
    )
    HIGHLIGHT_FMT = '[{i}]({link})'
    LINE_DELIM = '\n\n'

    @staticmethod
    def ig_users_in(body):
        """
        Returns a list of instagram usernames present in a reply body
                (if there are no usernames found, returns an empty list)
        """
        import re

        try:
            header_re = Formatter.HEADER_REGEX
        except AttributeError:
            # escape special characters so we can format the header into a
            # regex pattern
            escaped_header = re.sub(
                    # match any '[', ']', '(', or ')'
                    r'([\[\]\(\)])',
                    # escape the matched character
                    r'\\\1',
                    Formatter.HEADER_FMT
            )
            pattern = escaped_header.format(user='([\w\.]+)', link='.+')
            header_re = re.compile(pattern)
            Formatter.HEADER_REGEX = header_re

        return header_re.findall(body)

    def __init__(self, username):
        # wrap the string in a list so it is easier to work with
        self.FOOTER = [Formatter.FOOTER_FMT.format(
                contact_url=CONTACT_URL,
                source_url=REPO_URL,
                blacklist_url=BLACKLIST_URL_FMT.format(
                    to=username,
                ),
                help_url=HELP_URL,
        )]

    def __str__(self):
        return self.__class__.__name__

    def format(self, ig_list):
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

        for ig in ig_list:
            header = Formatter.HEADER_FMT.format(user=ig.user, link=ig.url)
            highlights = []
            media = ig.top_media
            for i, media_link in enumerate(media):
                logger.id(logger.debug, self,
                        '[{i:>{pad}}/{num}] {color_user}: adding {link}',
                        i=i+1,
                        pad=get_padding(len(media)),
                        num=len(media),
                        color_user=ig.user,
                        link=media_link,
                )
                highlights.append(Formatter.HIGHLIGHT_FMT.format(
                    i=i, # could do i+1 to start at 1 but whatever
                    link=media_link,
                ))

            current_reply.append(header)
            current_reply.append(' '.join(highlights))
            ig_users.append(ig)

            # try to add the current reply if its character length exceeds
            # the limit
            current_reply, ig_users = self.__try_add_reply(
                    replies,
                    current_reply,
                    ig_users,
            )

        # add the final reply to the replies list
        current_reply, ig_users = self.__try_add_reply(
                replies,
                current_reply,
                ig_users,
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

    def __try_add_reply(self, replies, current_reply, ig_users, force=False):
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
        full_reply = Formatter.LINE_DELIM.join(current_reply + self.FOOTER)
        while len(full_reply) >= Formatter.COMMENT_CHARACTER_LIMIT:
            # the total size of the current reply exceeds the maximum allowed
            # comment character length

            # truncate individual ig_user highlights from the end of the reply
            # until the reply is under the character limit
            idx -= step
            full_reply = Formatter.LINE_DELIM.join(
                    current_reply[:idx] + self.FOOTER
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

