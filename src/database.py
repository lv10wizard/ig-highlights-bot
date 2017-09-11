import abc
import os
import sqlite3

from utillib import logger


class FailedInit(Exception):
    def __init__(self, error, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.error = error

class Database(object):
    """
    Data storage handling (replied comments, etc) abstract base class
    """

    __metaclass__ = abc.ABCMeta

    @staticmethod
    def resolve_path(path):
        if path == ':memory:':
            return path
        return os.path.realpath( os.path.abspath( os.path.expanduser(path) ) )

    def __init__(self, path):
        self.path = path
        self._resolved_path = Database.resolve_path(path)
        self._dirname = os.path.dirname(path)
        self._resolved_dirname = Database.resolve_path(self._dirname)
        self._basename = os.path.basename(path)

    def __str__(self):
        return self._basename

    @property
    def _db(self):
        """
        Memoized database connection instance
        """
        db = None
        try:
            db = self.__the_connection

        except AttributeError:
            self.__the_connection = self.__init_db()
            db = self.__the_connection

        return db

    def __init_db(self):
        if (
                # check that _resolved_dirname is not the empty string in case
                # path == ':memory:'
                self._resolved_dirname
                and not os.path.exists(self._resolved_dirname)
        ):
            logger.prepend_id(logger.debug, self,
                    'Creating directories \'{dirname}\' ...',
                    dirname=self._dirname,
            )
            try:
                os.makedirs(self._resolved_dirname)
            except OSError as e:
                raise FailedInit(e, e.message)

        logger.prepend_id(logger.debug, self,
                'Opening connection to \'{path}\' ...',
                path=self.path,
        )

        try:
            db = sqlite3.connect(self._resolved_path)

        except sqlite3.OperationalError as e:
            raise FailedInit(e, e.message, self._resolved_path)

        else:

            def create_table(table):
                if not isinstance(table, basestring):
                    raise TypeError(
                            'create_table string expected, got {type}'
                            ' (\'{data}\')'.format(
                                type=type(table),
                                data=table,
                            )
                    )
                db.execute('CREATE TABLE IF NOT EXISTS {0}'.format(table))

            try:
                if isinstance(self._create_table_data, basestring):
                    create_table(self._create_table_data)
                elif isinstance(self._create_table_data, (list, tuple)):
                    for table in self._create_table_data:
                        create_table(table)
                else:
                    # programmer error
                    raise TypeError(
                            'Unhandled _create_table_data'
                            ' type=\'{type}\''.format(
                                type=type(self._create_table_data)
                            )
                    )
                db.commit()

            except sqlite3.DatabaseError as e:
                db.close()
                raise FailedInit(e, e.message)

            else:
                # https://docs.python.org/2/library/sqlite3.html#row-objects
                db.row_factory = sqlite3.Row
        return db

    def insert(self, *args, **kwargs):
        """
        Wrapper to non-abstract _insert method
        """
        try:
            self._insert(*args, **kwargs)

        except sqlite3.IntegrityError as e:
            # probably UNIQUE constraint failed
            logger.prepend_id(logger.error, self,
                    'INSERT Failed!'
                    '\n\targs={args}'
                    '\n\tkwargs={kwargs}', e,
                    args=args,
                    kwargs=kwargs,
            )

    @abc.abstractproperty
    def _create_table_data(self): pass

    @abc.abstractmethod
    def _insert(self, *args, **kwargs): pass

    # TODO? needed?
    @abc.abstractmethod
    def delete(self, *args, **kwargs): pass
    @abc.abstractmethod
    def udpate(self, *args, **kwargs): pass

class ReplyDatabase(Database):
    """
    Storage of all replies made by the bot
    """

    @property
    def _create_table_data(self):
        return (
                'comments('
                '   comment_id TEXT PRIMARY KEY'
                '   submission_id TEXT NOT NULL,'
                '   ig_user TEXT NOT NULL,'
                # apply unique constraint on specified keys
                # https://stackoverflow.com/a/15822009
                '   UNIQUE(submission_id, ig_user)'
                ')'
        )

    def _insert(self, comment, ig):
        with self._db as connection:
            connection.execute(
                    'INSERT INTO comments(comment_id, submission_id, ig_user)'
                    ' VALUES(?, ?, ?)',
                    (comment.id, comment.submission.id, ig.user.lower()),
            )

    def replied_comments_for_submission(self, submission_id):
        """
        Returns a list of comment ids that the bot has replied to for a given
        post
        """
        cursor = self._db.execute(
                'SELECT comment_id FROM comments WHERE submission_id = ?',
                (submission_id,),
        )
        return [row['comment_id'] for row in cursor]

    def replied_ig_users_for_submission(self, submission_id):
        """
        Returns the list of instagram user names that the bot has replied with
        for a given post
        """
        cursor = self._db.execute(
                'SELECT ig_user FROM comments WHERE submission_id = ?',
                (submission_id,),
        )
        return [row['ig_user'] for row in cursor]

    def has_replied(self, comment):
        """
        Returns True if the bot has replied to the specified comment
        """
        cursor = self._db.execute(
                'SELECT comment_id FROM comments WHERE comment_id = ?',
                (comment.id,),
        )
        return bool(cursor.fetchone())


__all__ = [
]

