from ._database import Database


class ReplyDatabase(Database):
    """
    Storage of all replies made by the bot
    """

    PATH = Database.PATH_FMT.format('replies.db')

    def __init__(self):
        Database.__init__(self, ReplyDatabase.PATH)

    @property
    def _create_table_data(self):
        return (
                'comments('
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   comment_fullname TEXT NOT NULL,'
                '   submission_fullname TEXT NOT NULL,'
                # case-insensitive
                # https://stackoverflow.com/a/973785
                '   ig_user TEXT NOT NULL COLLATE NOCASE,'
                # apply unique constraint on specified keys
                # https://stackoverflow.com/a/15822009
                '   UNIQUE(submission_fullname, ig_user)'
                ')'
        )

    def _insert(self, comment, ig_list):
        def get_user(ig):
            try:
                return ig.user
            except AttributeError:
                # probably a string
                return ig

        if isinstance(ig_list, (list, tuple)):
            values = [
                    (
                        comment.fullname,
                        comment.submission.fullname,
                        get_user(ig),
                    )
                    for ig in ig_list
            ]
        else:
            # assume ig_list is a single Instagram instance
            values = [
                    (
                        comment.fullname,
                        comment.submission.fullname,
                        get_user(ig_list),
                    )
            ]

        connection.executemany(
                'INSERT INTO comments('
                '   comment_fullname, submission_fullname, ig_user'
                ') VALUES(?, ?, ?)', values,
        )

    def replied_comments_for_submission(self, submission):
        """
        Returns a set of comment fullnames that the bot has replied to for a
        given post
        """
        cursor = self._db.execute(
                'SELECT comment_fullname FROM comments'
                ' WHERE submission_fullname = ?',
                (submission.fullname,),
        )
        return set([row['comment_fullname'] for row in cursor])

    def replied_ig_users_for_submission(self, submission):
        """
        Returns the set of instagram user names that the bot has replied with
        for a given post
        """
        cursor = self._db.execute(
                'SELECT ig_user FROM comments WHERE submission_fullname = ?',
                (submission.fullname,),
        )
        return set([row['ig_user'] for row in cursor])

    def has_replied(self, comment):
        """
        Returns True if the bot has replied to the specified comment
        """
        cursor = self._db.execute(
                'SELECT comment_fullname FROM comments'
                ' WHERE comment_fullname = ?',
                (comment.fullname,),
        )
        return bool(cursor.fetchone())


__all__ = [
        'ReplyDatabase',
]

