from _database import Database


class MessagesDatabase(Database):
    """
    Database of seen inbox messages.

    This is used instead of the read/unread flag so that anyone logging into
    the bot account and reading all the inbox messages will have no effect on
    message processing.
    """

    def _create_table_data(self):
        return (
                'messages('
                '   message_fullname TEXT PRIMARY KEY'
                ')'
        )

    def _insert(self, message):
        with self._db as connection:
            connection.execute(
                    'INSERT INTO messages(message_fullname) VALUES(?)',
                    (message.fullname,),
            )

    def has_seen(self, message):
        cursor = self._db.execute(
                'SELECT message_fullname FROM messages'
                ' WHERE message_fullname = ?',
                (message.fullname,),
        )
        return bool(cursor.fetchone())


__all__ = [
        'MessagesDatabase',
]

