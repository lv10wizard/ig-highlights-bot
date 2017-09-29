import time

from ._database import Database


class ReplyQueueDatabase(Database):
    """
    Persistent queue of comments the bot should reply to
    """

    PATH = Database.PATH_FMT.format('reply-queue.db')

    def __init__(self):
        Database.__init__(self, ReplyQueueDatabase.PATH)

    def __contains__(self, comment):
        cursor = self._db.execute(
                'SELECT comment_id FROM queue WHERE comment_id = ?',
                (comment.id,),
        )
        return bool(cursor.fetchone())

    def _create_table_data(self):
        return (
                'queue('
                '   comment_id TEXT PRIMARY KEY NOT NULL,'
                '   timestamp REAL NOT NULL,'
                '   mention_id TEXT'
                ')'
        )

    def _insert(self, comment, mention=None):
        self._db.execute(
                'INSERT INTO queue(comment_id, timestamp, mention_id)'
                ' VALUES(?, ?, ?)',
                (comment.id, time.time(), mention and mention.id),
        )

    def _update(self, comment):
        self._db.execute(
                'UPDATE queue SET timestamp = ? WHERE comment_id = ?',
                (time.time(), comment.id),
        )

    def _delete(self, comment):
        self._db.execute(
                'DELETE FROM queue WHERE comment_id = ?',
                (comment.id,),
        )

    def size(self):
        cursor = self._db.execute('SELECT count(*) FROM queue')
        return cursor.fetchone()[0]

    def get(self):
        """
        Returns (comment_id, mention_id) of the oldest record in the database
                or None if the queue is empty
        """
        cusor = self._db.execute(
                'SELECT comment_id, mention_id FROM queue'
                ' ORDER BY timestamp ASC'
        )
        row = cursor.fetchone()
        if row:
            return (row['comment_id'], row['mention_id'])
        return None


__all__ = [
        'ReplyQueueDatabase',
]

