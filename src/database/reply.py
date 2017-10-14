from ._database import Database
from src.util import logger


class ReplyDatabase(Database):
    """
    Storage of all replies made by the bot
    """

    PATH = Database.PATH_FMT.format('replies.db')

    def __init__(self):
        Database.__init__(self, ReplyDatabase.PATH)

    @property
    def _create_table_data(self):
        return (
                'comments('
                '   uid INTEGER PRIMARY KEY NOT NULL,'
                '   replied_fullname TEXT NOT NULL,'
                '   submission_fullname TEXT NOT NULL,'
                # case-insensitive
                # https://stackoverflow.com/a/973785
                '   ig_user TEXT NOT NULL COLLATE NOCASE,'
                # apply unique constraint on specified keys
                # https://stackoverflow.com/a/15822009
                '   UNIQUE(submission_fullname, ig_user)'
                ')'
        )

    def _insert(self, thing, ig_list):
        from src import reddit

        def get_user(ig):
            try:
                return ig.user
            except AttributeError:
                # probably a string
                return ig

        submission = reddit.get_submission_for(thing)
        if not submission:
            # TODO? raise? not recording a reply could result in the bot
            # replying multiple times to the same thing
            logger.id(logger.warn, self,
                    'Could not insert {color_thing} ({color_list}):'
                    ' no submission found!',
                    color_thing=reddit.display_id(thing),
                    color_list=ig_list,
            )
            return

        if isinstance(ig_list, (list, tuple)):
            values = [
                    (
                        thing.fullname,
                        submission.fullname,
                        get_user(ig),
                    )
                    for ig in ig_list
            ]
        else:
            # assume ig_list is a single Instagram instance
            values = [
                    (
                        thing.fullname,
                        submission.fullname,
                        get_user(ig_list),
                    )
            ]

        self._db.executemany(
                'INSERT INTO comments('
                '   replied_fullname, submission_fullname, ig_user'
                ') VALUES(?, ?, ?)', values,
        )

    def replied_things_for_submission(self, submission):
        """
        Returns a set of thing fullnames that the bot has replied to for a
        given post
        """
        cursor = self._db.execute(
                'SELECT replied_fullname FROM comments'
                ' WHERE submission_fullname = ?',
                (submission.fullname,),
        )
        return set([row['replied_fullname'] for row in cursor])

    def replied_ig_users_for_submission(self, submission):
        """
        Returns the set of instagram user names that the bot has replied with
        for a given post
        """
        cursor = self._db.execute(
                'SELECT ig_user FROM comments WHERE submission_fullname = ?',
                (submission.fullname,),
        )
        return set([row['ig_user'] for row in cursor])

    def has_replied(self, thing):
        """
        Returns True if the bot has replied to the specified thing
        """
        cursor = self._db.execute(
                'SELECT replied_fullname FROM comments'
                ' WHERE replied_fullname = ?',
                (thing.fullname,),
        )
        return bool(cursor.fetchone())


__all__ = [
        'ReplyDatabase',
]

