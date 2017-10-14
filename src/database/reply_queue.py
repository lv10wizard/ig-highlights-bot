import time

from ._database import Database


class ReplyQueueDatabase(Database):
    """
    Persistent queue of comments the bot should reply to
    """

    PATH = Database.PATH_FMT.format('reply-queue.db')

    @staticmethod
    def get_fullname(thing):
        try:
            return thing.fullname
        except AttributeError:
            return thing

    def __init__(self):
        Database.__init__(self, ReplyQueueDatabase.PATH)

    def __contains__(self, thing):
        cursor = self._db.execute(
                'SELECT thing_fullname FROM queue WHERE thing_fullname = ?',
                (ReplyQueueDatabase.get_fullname(thing),),
        )
        return bool(cursor.fetchone())

    @property
    def _create_table_data(self):
        return (
                'queue('
                '   thing_fullname TEXT PRIMARY KEY NOT NULL,'
                '   timestamp REAL NOT NULL,'
                '   mention_id TEXT'
                ')'
        )

    def _insert(self, thing, mention=None):
        self._db.execute(
                'INSERT INTO queue(thing_fullname, timestamp, mention_id)'
                ' VALUES(?, ?, ?)',
                (
                    ReplyQueueDatabase.get_fullname(thing),
                    time.time(),
                    mention and mention.id
                ),
        )

    def _update(self, thing):
        self._db.execute(
                'UPDATE queue SET timestamp = ? WHERE thing_fullname = ?',
                (time.time(), ReplyQueueDatabase.get_fullname(thing)),
        )

    def _delete(self, thing):
        self._db.execute(
                'DELETE FROM queue WHERE thing_fullname = ?',
                (ReplyQueueDatabase.get_fullname(thing),),
        )

    def size(self):
        cursor = self._db.execute('SELECT count(*) FROM queue')
        return cursor.fetchone()[0]

    def get(self):
        """
        Returns (thing_fullname, mention_id) of the oldest record in the
                    database
                or None if the queue is empty
        """
        cursor = self._db.execute(
                'SELECT thing_fullname, mention_id FROM queue'
                ' ORDER BY timestamp ASC'
        )
        row = cursor.fetchone()
        if row:
            return (row['thing_fullname'], row['mention_id'])
        return None


__all__ = [
        'ReplyQueueDatabase',
]

