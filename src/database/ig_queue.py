import time

from _database import Database


class InstagramQueueDatabase(Database):
    """
    Persistent queue of instagram data to-be fetched and reddit data to-be
    replied to
    """

    def __init__(self, *args, **kwargs):
        Database.__init__(self, *args, **kwargs)
        # alias database methods so they look more like queue methods
        self.put = self.insert

    def _create_table_data(self):
        return (
                'queue('
                '   comment_id TEXT PRIMARY KEY NOT NULL,'
                '   ig_user TEXT NOT NULL COLLATE NOCASE,'
                '   last_id TEXT,'
                '   timestamp REAL NOT NULL'
                ')'
        )

    def _insert(self, ig_user, comment, last_id=None):
        self._db.execute(
                'INSERT INTO queue(comment_id, ig_user, last_id, timestamp)'
                ' VALUES(?, ?, ?, ?)',
                (comment.id, ig_user, last_id, time.time()),
        )

    def _delete(self, comment):
        self._db.execute(
                'DELETE FROM queue WHERE comment_id = ?',
                (comment.id,),
        )

    def get(self):
        """
        Gets the first element in the queue (ie, the oldest record)

        Returns (comment_id, ig_user, last_id)
                (None, None, None) if the queue is empty
        """
        cursor = self._db.execute(
                'SELECT comment_id, ig_user, last_id'
                ' FROM queue'
                ' ORDER BY timestamp ASC',
        )

        comment_id = None
        ig_user = None
        last_id = None
        row = cursor.fetchone()
        if row:
            comment_id = row['comment_id']
            ig_user = row['ig_user']
            last_id = row['last_id']

        return comment_id, ig_user, last_id


__all__ = [
        'InstagramQueueDatabase',
]

