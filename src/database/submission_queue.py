import time

from ._database import Database


class SubmissionQueueDatabase(Database):
    """
    Persistent queue of submissions the bot has been summoned to. This stores
    the mentions' submissions which have not yet been processed.

    Note: this class is NOT process-safe for multiple consumers
    """

    PATH = Database.PATH_FMT.format('submission-queue.db')

    def __init__(self):
        Database.__init__(self, SubmissionQueueDatabase.PATH)

    def __contains__(self, submission):
        cursor = self._db.execute(
                'SELECT submission_id FROM queue WHERE submission_id = ?',
                (submission.id,),
        )
        return bool(cursor.fetchone())

    def _create_table_data(self):
        return (
                'queue('
                # key by the summoned comment since they should be unique
                '   comment_id TEXT PRIMARY KEY NOT NULL,'
                '   submission_id TEXT NOT NULL,'
                # timestamp for ordering
                '   timestamp REAL NOT NULL'
                ')'
        )

    def _insert(self, comment, submission):
        self._db.execute(
                'INSERT INTO queue(comment_id, submission_id, timestamp)'
                ' VALUES(?, ?)',
                (comment.id, submission.id, time.time()),
        )

    def _delete(self, comment, submission):
        self._db.execute(
                'DELETE FROM queue WHERE comment_id = ? AND submission_id = ?',
                (comment.id, submission.id),
        )

    def _update(self, comment, submission):
        self._db.execute(
                'UPDATE queue SET timestamp = ?'
                ' WHERE comment_id = ?'
                ' AND submission_id = ?'
                (time.time(), comment.id, submission.id),
        )

    def size(self):
        cursor = self._db.execute('SELECT count(*) FROM queue')
        return cursor.fetchone()[0]

    def get(self):
        """
        Returns the first enqueued (comment_id, submission_id)
                or None if the queue is empty
            Note: DOES NOT remove the row from the database
        """
        cursor = self._db.execute(
                'SELECT comment_id, submission_id FROM queue'
                ' ORDER BY timestamp ASC'
        )
        row = cursor.fetchone()
        if row:
            return (row['comment_id'], row['submission_id'])
        return None


__all__ = [
        'SubmissionQueueDatabase',
]

