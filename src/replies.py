import urllib

from utillib import logger

from constants import (
        BLACKLIST_URL_FMT,
        CONTACT_URL_FMT,
        HELP_URL,
        REPO_URL,
)


class Formatter(object):
    """
    """

    COMMENT_CHARACTER_LIMIT = 1e4
    HEADER_FMT = '[{user}]({link}) highlights:'
    FOOTER_FMT = (
            '---\n^Beep ^Boop. ^I ^am ^definitely ^human.'
            ' ^[[Contact]({contact_url})]'
            ' ^[[Source]({source_url})]'
            ' ^[[Blacklist]({blacklist_url})]'
            ' ^[[Help]({help_url})]'
    )
    HIGHLIGHT_FMT = '[{i}]({link})'
    LINE_DELIM = '\n\n'

    def __init__(self, praw_config):
        # wrap the string in a list so it is easier to work with
        self.FOOTER = list(Formatter.FOOTER.format(
                contact_url=CONTACT_URL_FMT.format(
                    subject=urllib.quote('Instagram highlights bot'),
                ),
                source_url=REPO_URL,
                blacklist_url=BLACKLIST_URL_FMT.format(
                    # XXX: does not verify that this is even set
                    to=praw_config.username,
                ),
                help_url=HELP_URL,
        ))

    def format(ig_list, num_highlights):
        """
        Formats the data into one or more reddit comment reply strings

        Returns a list of strings (each len(string) <= COMMENT_CHARACTER_LIMIT)
        """
        replies = []
        current_reply = []

        for ig in ig_list:
            header = Formatter.HEADER_FMT.format(user=ig.user, link=ig.url)
            highlights = []
            for i in xrange(num_highlights):
                highlights.append(Formatter.HIGHLIGHT_FMT.format(
                    i=i, # could do i+1 to start at 1 but whatever
                    link=ig.links_by_likes[i],
                ))

                # try to add the current reply if its character length exceeds
                # the limit
                if self.__try_add_reply(replies, current_reply):
                    # the current reply was added; start a new reply
                    current_reply = []

            current_reply.append(header)
            current_reply.append(' '.join(highlights))
        # add the final reply to the replies list
        self.__try_add_reply(replies, current_reply, force=True)

        return replies

    def __try_add_reply(self, replies, current_reply, force=False):
        did_add = False
        full_reply = Formatter.LINE_DELIM.join(current_reply + self.FOOTER)
        if force or len(full_reply) > Formatter.COMMENT_CHARACTER_LIMIT:
            # the total size of the current reply exceeds the maximum allowed
            # comment character length
            replies.append(full_reply)
            did_add = True
        return did_add


__all__ = [
        'Formatter',
]

