import abc
import os
import pprint
import re
import sqlite3

from utillib import logger

from src import config


class BaseDatabaseException(Exception): pass

class UniqueConstraintFailed(BaseDatabaseException): pass
class NotNullConstraintFailed(BaseDatabaseException): pass
class CheckConstraintFailed(BaseDatabaseException): pass

class FailedInit(BaseDatabaseException):
    def __init__(self, error, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.error = error

class _SqliteConnectionWrapper(object):
    """
    SQLite Connection wrapper (for logging)
    """

    def __init__(self, connection, id):
        self.connection = connection
        self.id = id

    def __str__(self):
        return self.id

    def __getattr__(self, attr):
        return getattr(self.connection, attr)

    def __construct_msg(self, *args, **kwargs):
        msg = ['{sql}']
        if args:
            msg.append('args: {args}')
        if kwargs:
            msg.append('kwargs: {kwargs}')
        return msg

    def execute(self, sql, *args, **kwargs):
        logger.prepend_id(logger.debug, self,
                '\n\t'.join(self.__construct_msg(*args, **kwargs)),
                sql=sql,
                args=args,
                kwargs=kwargs,
        )
        return self.connection.execute(sql, *args, **kwargs)

    def executemany(self, sql, *args, **kwargs):
        logger.prepend_id(logger.debug, self,
                '\n\t'.join(self.__construct_msg(*args, **kwargs)),
                sql=sql,
                args=args,
                kwargs=kwargs,
        )
        return self.connection.executemany(sql, *args, **kwargs)

class Database(object):
    """
    Data storage handling (replied comments, etc) abstract base class
    """

    __metaclass__ = abc.ABCMeta

    @staticmethod
    def resolve_path(path):
        if path == ':memory:':
            return path
        return config.resolve_path(path)

    @staticmethod
    def reraise_integrity_error(err):
        RE_FMT = r'^{0} constraint failed:'
        if re.search(RE_FMT.format('UNIQUE'), err.message):
            raise UniqueConstraintFailed(err.message)

        elif re.search(RE_FMT.format('NOT NULL'), err.message):
            raise NotNullConstraintFailed(err.message)

        elif re.search(RE_FMT.format('CHECK'), err.message):
            raise CheckConstraintFailed(err.message)

        # passed a random error ...?
        raise

    def __init__(self, path):
        self.path = path
        self._resolved_path = Database.resolve_path(path)
        self._dirname = os.path.dirname(path)
        self._resolved_dirname = Database.resolve_path(self._dirname)
        self._basename = os.path.basename(path)

    def __str__(self):
        return self._basename

    def __enter__(self):
        return self._db

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None and exc_value is None and traceback is None:
            self._db.commit()
        else:
            logger.prepend_id(logger.error, self,
                    'An error occurred! Rolling back changes ...', exc_value,
            )
            self._db.rollback()
            # TODO? suppress error ?
            # return True

    @property
    def _db(self):
        """
        Memoized database connection instance
        """
        db = None
        try:
            db = self.__the_connection

        except AttributeError:
            self.__the_connection = _SqliteConnectionWrapper(
                    connection=self.__init_db(),
                    id=self._basename,
            )
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

                try:
                    self._initialize_tables(db)
                except sqlite3.IntegrityError:
                    # probably attempted a duplicate INSERT (UNIQUE
                    # constraint)
                    # => tables were already initialized
                    pass

                db.commit()

            except sqlite3.DatabaseError as e:
                db.close()
                raise FailedInit(e, e.message)

            else:
                # https://docs.python.org/2/library/sqlite3.html#row-objects
                db.row_factory = sqlite3.Row
        return db

    def commit(self):
        self._db.commit()

    def rollback(self):
        self._db.rollback()

    def insert(self, *args, **kwargs):
        """
        Wrapper to abstract _insert method
        """
        try:
            self._insert(*args, **kwargs)

        except sqlite3.IntegrityError as e:
            Database.reraise_integrity_error(e)

        except Exception as e:
            # probably UNIQUE or CHECK constraint failed
            # or could be something more nefarious...
            logger.prepend_id(logger.error, self,
                    'INSERT Failed!'
                    '\n\targs={args}'
                    '\n\tkwargs={kwargs}', e,
                    args=args,
                    kwargs=kwargs,
            )

    def delete(self, *args, **kwargs):
        """
        Wrapper to overrideable _delete method
        """
        try:
            self._delete(*args, **kwargs)

        except sqlite3.IntegrityError as e:
            Database.reraise_integrity_error(e)

        except Exception as e:
            logger.prepend_id(logger.error, self,
                    'DELETE Failed!'
                    '\n\targs={args}'
                    '\n\tkwargs={kwargs}', e,
                    args=args,
                    kwargs=kwargs,
            )

    def update(self, *args, **kwargs):
        """
        Wrapper to overrideable _update method
        """
        try:
            self._update(*args, **kwargs)

        except sqlite3.IntegrityError as e:
            Database.reraise_integrity_error(e)

        except Exception as e:
            logger.prepend_id(logger.error, self,
                    'UPDATE Failed!'
                    '\n\targs={args}'
                    '\n\tkwargs={kwargs}', e,
                    args=args,
                    kwargs=kwargs,
            )

    def _initialize_tables(self, db):
        """
        Overrideable method for child classes to do extra initialization of
        tables after creation.

        ** IMPORTANT: self._db should not be referenced within this method **
        Instead, use the db parameter.
        """
        pass

    @abc.abstractproperty
    def _create_table_data(self): pass

    @abc.abstractmethod
    def _insert(self, *args, **kwargs): pass

    def _delete(self, *args, **kwargs): pass

    def _update(self, *args, **kwargs): pass


__all__ = [
        'BaseDatabaseException',
        'UniqueConstraintFailed',
        'NotNullConstraintFailed',
        'CheckConstraintFailed',
        'FailedInit',
        'Database',
]

