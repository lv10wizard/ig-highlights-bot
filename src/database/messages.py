from ._database import Database


class MessagesDatabase(Database):
    """
    Database of seen inbox messages.

    This is used instead of the read/unread flag so that anyone logging into
    the bot account and reading all the inbox messages will have no effect on
    message processing.
    """

    PATH = 'messages.db'

    @property
    def _create_table_data(self):
        return (
                'messages('
                '   message_fullname TEXT PRIMARY KEY'
                ')'
        )

    def _insert(self, message):
        from src import reddit

        self._db.execute(
                'INSERT INTO messages(message_fullname) VALUES(?)',
                (reddit.fullname(message),),
        )

    def has_seen(self, message):
        from src import reddit

        cursor = self._db.execute(
                'SELECT message_fullname FROM messages'
                ' WHERE message_fullname = ?',
                (reddit.fullname(message),),
        )
        return bool(cursor.fetchone())


__all__ = [
        'MessagesDatabase',
]

