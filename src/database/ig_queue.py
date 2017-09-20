import time

# XXX: requests is already a dependency so may as well reuse this
from requests.structures import CaseInsensitiveDict

from ._database import Database


class InstagramQueueDatabase(Database):
    """
    Persistent queue of instagram data to-be fetched and reddit data to-be
    replied to
    """

    def __init__(self, *args, **kwargs):
        Database.__init__(self, *args, **kwargs)

    def __contains__(self, comment):
        cursor = self._db.execute(
                'SELECT FROM queue WHERE comment_id = ?',
                (comment.id,),
        )
        return bool(cursor.fetchone())

    def _create_table_data(self):
        return (
                'queue('
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   comment_id TEXT NOT NULL,'
                '   ig_user TEXT NOT NULL COLLATE NOCASE,'
                '   last_id TEXT,'
                '   timestamp REAL NOT NULL,'
                '   UNIQUE(comment_id, ig_user)'
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

    def _update(self, comment):
        """
        Updates the timestamp for a given comment effectively moving it to the
        back of the queue
        """
        self._db.execute(
                'UPDATE queue SET timestamp = ? WHERE comment_id = ?',
                (time.time(), comment.id),
        )

    def size(self):
        """
        Returns the current number of elements in the database
        """
        cursor = self._db.execute('SELECT comment_id FROM queue')
        # the database treats each unique comment as a queue element
        return len(set(row['comment_id'] for row in cursor))

    def get(self):
        """
        Gets the first queued comment_id

        Returns comment_id of the oldest record in the database
                or None if the queue is empty
        """
        cursor = self._db.execute(
                'SELECT comment_id FROM queue ORDER BY timestamp ASC'
        )
        row = cursor.fetchone()
        if row:
            return row['comment_id']
        return None

    def get_ig_data_for(self, comment):
        """
        Returns a case-insensitive dictionary {ig_user: last_id}

                or an empty ditionary if the comment is not queued
        """
        cursor = self._db.execute(
                'SELECT ig_user, last_id FROM queue WHERE comment_id = ?',
                (comment.id,)
        )
        return CaseInsensitiveDict(
                {row['ig_user']: row['last_id'] for row in cursor}
        )

    def is_queued(self, ig_user, comment):
        """
        Returns whether the (ig_user, comment) pair is in the queue
        """
        cursor = self._db.execute(
                'SELECT comment_id FROM queue'
                ' WHERE ig_user = ? AND comment_id = ?',
                (ig_user, comment.id),
        )
        return bool(cursor.fetchone())


__all__ = [
        'InstagramQueueDatabase',
]

