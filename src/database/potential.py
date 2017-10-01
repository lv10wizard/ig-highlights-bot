from six import integer_types

from ._database import Database


class PotentialSubredditsDatabase(Database):
    """
    Database of successful summoned-to subreddits. This is essentially a counter
    for subreddits which may be added to the bot's default set of crawled
    subreddits.
    """

    PATH = Database.PATH_FMT.format('to-add-subreddits.db')

    def __init__(self):
        Database.__init__( self, PotentialSubredditsDatabase.PATH)

    @property
    def _create_table_data(self):
        return (
                'potential_subreddits('
                '   subreddit_name TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,'
                '   count INTEGER NOT NULL'
                ')'
        )

    def _insert(self, thing):
        """
        Inserts a new subreddit or increments the to-add count for the given
        subreddit
        """
        count = self.count(thing)
        if count < 0:
            self._db.execute(
                    'INSERT INTO potential_subreddits(subreddit_name, count)'
                    ' VALUES(?, ?)',
                    (thing.subreddit.display_name, 1),
            )

        else:
            self.update(thing, count)

    def _delete(self, thing):
        """
        Removes the thing's subreddit from the database
        """
        self._db.execute(
                'DELETE FROM potential_subreddits WHERE subreddit_name = ?',
                (thing.subreddit.display_name,),
        )

    def _update(self, thing, count=None):
        """
        Increments the to-add count of the given subreddit
        """
        if not isinstance(count, integer_types):
            count = self.count(thing)
        self._db.execute(
                'UPDATE potential_subreddits'
                ' SET count = ?'
                ' WHERE subreddit_name = ?',
                (thing.subreddit.display_name, count+1),
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

