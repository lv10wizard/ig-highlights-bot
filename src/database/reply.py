from _database import Database


class ReplyDatabase(Database):
    """
    Storage of all replies made by the bot
    """

    @property
    def _create_table_data(self):
        return (
                'comments('
                '   comment_id TEXT PRIMARY KEY'
                '   submission_id TEXT NOT NULL,'
                # case-insensitive
                # https://stackoverflow.com/a/973785
                '   ig_user TEXT NOT NULL COLLATE NOCASE,'
                # apply unique constraint on specified keys
                # https://stackoverflow.com/a/15822009
                '   UNIQUE(submission_id, ig_user)'
                ')'
        )

    def _insert(self, comment, ig_list):
        if isinstance(ig_list, (list, tuple)):
            values = [
                    (comment.id, comment.submission.id, ig.user)
                    for ig in ig_list
            ]
        else:
            # assume ig_list is a single Instagram instance
            values = [(comment.id, comment.submission.id, ig_list.user)]

        with self._db as connection:
            connection.executemany(
                    'INSERT INTO comments(comment_id, submission_id, ig_user)'
                    ' VALUES(?, ?, ?)', values,
            )

    def replied_comments_for_submission(self, submission_id):
        """
        Returns a set of comment ids that the bot has replied to for a given
        post
        """
        cursor = self._db.execute(
                'SELECT comment_id FROM comments WHERE submission_id = ?',
                (submission_id,),
        )
        return set([row['comment_id'] for row in cursor])

    def replied_ig_users_for_submission(self, submission_id):
        """
        Returns the set of instagram user names that the bot has replied with
        for a given post
        """
        cursor = self._db.execute(
                'SELECT ig_user FROM comments WHERE submission_id = ?',
                (submission_id,),
        )
        return set([row['ig_user'] for row in cursor])

    def has_replied(self, comment):
        """
        Returns True if the bot has replied to the specified comment
        """
        cursor = self._db.execute(
                'SELECT comment_id FROM comments WHERE comment_id = ?',
                (comment.id,),
        )
        return bool(cursor.fetchone())


__all__ = [
        'ReplyDatabase',
]

