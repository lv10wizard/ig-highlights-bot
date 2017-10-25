from ._database import Database


class BadUsernamesDatabase(Database):
    """
    Strings that should not be matched as potential usernames
    """

    PATH = 'bad_usernames.db'

    @staticmethod
    def get_fullname(thing):
        try:
            submission = thing.submission
        except AttributeError:
            submission = thing

        try:
            return submission.fullname
        except AttributeError:
            # in case 'thing' is a string
            return submission

    def __init__(self, dry_run=False, *args, **kwargs):
        # don't save a distinct database for dry-runs
        Database.__init__(self, dry_run=False, *args, **kwargs)

    def __contains__(self, text):
        cursor = self._db.execute(
                'SELECT string FROM bad_usernames WHERE string = ?',
                (text,),
        )
        return bool(cursor.fetchone())

    @property
    def _create_table_data(self):
        return (
                'bad_usernames('
                '   string TEXT PRIMARY KEY NOT NULL COLLATE NOCASE,'
                '   thing_fullname TEXT NOT NULL,'
                '   score INTEGER DEFAULT -1'
                ')'
        )

    def _insert(self, text, thing, score=None):
        from src import reddit

        self._db.execute(
                'INSERT INTO bad_usernames(string, thing_fullname, score)'
                ' VALUES(?, ?, ?)',
                (
                    text,
                    BadUsernamesDatabase.get_fullname(thing),
                    # try the thing first; fallback to the provided value in
                    # case thing is a string
                    reddit.score(thing) or score,
                ),
        )

    def _delete(self, text):
        self._db.execute(
                'DELETE FROM bad_usernames WHERE string = ?',
                (text,),
        )

    def get_bad_username_strings_raw(self):
        """
        Returns the set of bad username strings exactly as they appear in the
                database
        """
        cursor = self._db.execute('SELECT string FROM bad_usernames')
        return set(row['string'] for row in cursor)

    def get_bad_username_patterns(self):
        """
        Returns the bad username strings as a set of regex patterns
            eg.
            >>> patterns = bad_usernames.get_bad_username_patterns()
            >>> bad_username_regex = re.compile('|'.join(patterns))
            >>> bad_username_regex.search(text)
        """
        from src.util import format_repeat_each_character_pattern
        bad_usernames = self.get_bad_username_strings_raw()
        return set(map(format_repeat_each_character_pattern, bad_usernames))


__all__ = [
        'BadUsernamesDatabase',
]

