import time

from six import string_types

from ._database import Database
from src.config import parse_time
from src.util import logger


class InstagramQueueDatabase(Database):
    """
    Persistent queue of instagram data to-be fetched and reddit data to-be
    replied to (Note: not really a queue in the FIFO sense but in the delayed
    data sense)
    """

    PATH = 'ig-queue.db'
    STALE_THRESHOLD = parse_time('1d')

    @staticmethod
    def _do_callback(callback, ig_usernames):
        """
        Runs the callback method on the ig_usernames parameter based on its type

        Assumes a True return from the callback means that iteration no longer
                needs to occur on ig_usernames.
        """
        result = False
        if isinstance(ig_usernames, string_types):
            result = callback(ig_usernames)

        elif hasattr(ig_usernames, '__iter__'):
            for ig_user in ig_usernames:
                try:
                    # in case ig_usernames contains Instagram instances
                    ig_user = ig_user.user
                except AttributeError:
                    pass
                result = callback(ig_user)
                if result:
                    # return True if any of the specified users is in the
                    # database
                    break

        else:
            raise TypeError(
                    'Unrecognized ig_usernames type=\'{type}\''
                    ' ({ig_usernames}); str or iterable expected.'.format(
                        type=type(ig_usernames),
                        ig_usernames=ig_usernames,
                    )
            )

        return result

    def __init__(self, dry_run=False, *args, **kwargs):
        Database.__init__(self, dry_run=False, *args, **kwargs)

    def __contains__(self, ig_usernames):
        def contains_user(ig_user):
            cursor = self._db.execute(
                    'SELECT * FROM queue WHERE ig_user = ?',
                    (ig_user,),
            )
            return bool(cursor.fetchone())

        self.__reset_stale_data()
        return self._do_callback(contains_user, ig_usernames)

    @property
    def _create_table_data(self):
        return (
                'queue('
                '   ig_user TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,'
                '   last_id TEXT,'
                '   timestamp REAL NOT NULL'
                ')'
        )

    def __reset_stale_data(self):
        """
        Resets queued user data that is considered stale.
        """
        cursor = self._db.execute('SELECT ig_user, timestamp FROM queue')
        # looping manually over each item instead of a single UPDATE ... WHERE
        # query is probably slower but allows logging exactly which users were
        # modified.
        stale = set()
        for row in cursor:
            elapsed = time.time() - row['timestamp']
            if elapsed >= InstagramQueueDatabase.STALE_THRESHOLD:
                stale.add(row['ig_user'])

        if stale:
            logger.id(logger.debug, self,
                    'Resetting last_id of #{num} user{plural}: {color}',
                    num=len(stale),
                    plural=('' if len(stale) == 1 else 's'),
                    color=stale,
            )
            # reset the last_id of each stale user so that the next fetch for
            # them starts from the beginning
            with self._db:
                for ig_user in stale:
                    self._db.execute(
                            'UPDATE queue SET last_id = ? timestamp = ?'
                            ' WHERE ig_user = ?',
                            (None, time.time(), ig_user),
                    )

    def _insert(self, ig_user, last_id=None):
        if ig_user not in self:
            self._db.execute(
                    'INSERT INTO queue(ig_user, last_id, timestamp)'
                    ' VALUES(?, ?, ?)',
                    (ig_user, last_id, time.time()),
            )
        else:
            self.update(ig_user, last_id)

    def _delete(self, ig_usernames):
        def do_delete(ig_user):
            self._db.execute(
                    'DELETE FROM queue WHERE ig_user = ?',
                    (ig_user,),
            )

        return self._do_callback(do_delete, ig_usernames)

    def _update(self, ig_user, last_id=None):
        self._db.execute(
                'UPDATE queue SET last_id = ?, timestamp = ?'
                ' WHERE ig_user = ?',
                (last_id, time.time(), ig_user),
        )

    def size(self):
        """
        Returns the current number of elements in the database
        """
        cursor = self._db.execute('SELECT count(*) FROM queue')
        return cursor.fetchone()[0]

    def get_last_id_for(self, ig_user):
        """
        Returns the last_id stored for the given ig_user
                or None if the ig_user is not in the database
        """
        self.__reset_stale_data()

        last_id = None
        cursor = self._db.execute(
                'SELECT last_id FROM queue WHERE ig_user = ?',
                (ig_user,)
        )
        row = cursor.fetchone()
        if row:
            last_id = row['last_id']
        return last_id


__all__ = [
        'InstagramQueueDatabase',
]

