from ._database import Database


class PotentialSubredditsDatabase(Database):
    """
    """

    def _create_table_data(self):
        return (
                'potential_subreddits('
                '   subreddit_name TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,'
                '   count INTEGER NOT NULL,'
                ')'
        )

    def _insert(self, thing):
        """
        Increments the to-add count for the given subreddit
        """
        count = self.count(thing)
        if count < 0:
            self._db.execute(
                    'INSERT INTO potential_subreddits(subreddit_name, count)'
                    ' VALUES(?, ?)',
                    (thing.subreddit.display_name, 1),
            )

        else:
            self._db.execute(
                    'UPDATE potential_subreddits'
                    ' SET count = ?'
                    ' WHERE subreddit_name = ?',
                    (thing.subreddit.display_name, count+1),
            )

    def _delete(self, thing):
        """
        Removes the thing's subreddit from the database
        """
        self._db.execute(
                'DELETE FROM potential_subreddits WHERE subreddit_name = ?',
                (thing.subreddit.display_name,),
        )

    def count(self, thing):
        """
        Returns the to-add count for the given thing's subreddit
                -1 if the subreddit does not exist
        """
        cursor = self._db.execute(
                'SELECT count FROM potential_subreddits'
                ' WHERE subreddit_name = ?',
                (thing.subreddit.display_name,),
        )
        row = cursor.fetchone()
        return row['count'] if row else -1


__all__ = [
        'PotentialSubredditsDatabase',
]

