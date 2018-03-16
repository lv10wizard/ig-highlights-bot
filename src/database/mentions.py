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
                '   mention_fullname TEXT NOT NULL,'
                '   comment_author TEXT NOT NULL,'
                '   UNIQUE('
                '       submission_fullname,'
                '       mention_fullname,'
                '       comment_author'
                '   )'
                ')'
        )

    def _insert(self, mention):
        from src import reddit

        submission_fullname = reddit.fullname(
                reddit.get_submission_for(mention)
        )
        mention_fullname = reddit.fullname(mention)
        self._db.execute(
                'INSERT INTO'
                ' mentions('
                '   submission_fullname,'
                '   mention_fullname,'
                '   comment_author'
                ') VALUES(?, ?, ?)',
                # assumption: mention cannot itself be a submission
                (
                    submission_fullname,
                    mention_fullname,
                    reddit.author(mention, replace_none=False),
                ),
        )

    def has_seen(self, mention):
        """
        Returns True if the mention has been seen (ie, that the mention's author
        has already summoned the bot to that post)
        """
        from src import reddit

        mention_fullname = reddit.fullname(mention)
        cursor = self._db.execute(
                'SELECT mention_fullname FROM mentions'
                ' WHERE mention_fullname = ? AND comment_author = ?',
                (mention_fullname, reddit.author(mention, replace_none=False)),
        )
        return bool(cursor.fetchone())


__all__ = [
        'MentionsDatabase',
]

