from ._database import Database


class MentionsDatabase(Database):
    """
    Database of seen mention comments.
    """

    PATH = 'mentions.db'

    @property
    def _create_table_data(self):
        return (
                'mentions('
                '   uid INTEGER PRIMARY KEY,'
                '   submission_fullname TEXT NOT NULL,'
                '   comment_author TEXT NOT NULL,'
                '   UNIQUE(submission_fullname, comment_author)'
                ')'
        )

    def _insert(self, mention):
        from src import reddit

        fullname = reddit.fullname(reddit.get_submission_for(mention))
        self._db.execute(
                'INSERT INTO mentions(submission_fullname, comment_author)'
                ' VALUES(?, ?)',
                # assumption: mention cannot itself be a submission
                (fullname, mention.author.name),
        )

    def has_seen(self, mention):
        """
        Returns True if the mention has been seen (ie, that the mention's author
        has already summoned the bot to that post)
        """
        from src import reddit

        fullname = reddit.fullname(reddit.get_submission_for(mention))
        cursor = self._db.execute(
                'SELECT submission_fullname FROM mentions'
                ' WHERE submission_fullname = ? AND comment_author = ?',
                (fullname, mention.author.name),
        )
        return bool(cursor.fetchone())


__all__ = [
        'MentionsDatabase',
]

