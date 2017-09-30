import abc
import os
import pprint
import re
import sqlite3
import sys
import time

from six import (
        add_metaclass,
        string_types,
)

from constants import DATA_ROOT_DIR
from src import config
from src.util import logger


class BaseDatabaseException(Exception): pass
class BaseIntegrityException(sqlite3.IntegrityError, BaseDatabaseException):
    pass

class UniqueConstraintFailed(BaseIntegrityException): pass
class NotNullConstraintFailed(BaseIntegrityException): pass
class CheckConstraintFailed(BaseIntegrityException): pass

class FailedInit(BaseDatabaseException):
    def __init__(self, error, *args, **kwargs):
        Exception.__init__(self, *args, **kwargs)
        self.error = error

class _SqliteConnectionWrapper(object):
    """
    SQLite Connection wrapper (mainly for logging execute calls)
    """

    _LOCKED_RE = re.compile(r'database is locked', flags=re.IGNORECASE)

    INTEGRITY_RE_FMT = r'^{0} constraint failed:'
    _UNIQUE_RE = re.compile(INTEGRITY_RE_FMT.format('UNIQUE'))
    _NOTNULL_RE = re.compile(INTEGRITY_RE_FMT.format('NOT NULL'))
    _CHECK_RE = re.compile(INTEGRITY_RE_FMT.format('CHECK'))

    @staticmethod
    def get_err_msg(err):
        try:
            return err.message
        except AttributeError:
            try:
                return err.args[0]

            except (AttributeError, IndexError):
                # passed some random error?
                raise

    @staticmethod
    def reraise_integrity_error(err):
        message = _SqliteConnectionWrapper.get_err_msg(err)
        if _SqliteConnectionWrapper._UNIQUE_RE.search(message):
            raise UniqueConstraintFailed(message)

        elif _SqliteConnectionWrapper._NOTNULL_RE.search(message):
            raise NotNullConstraintFailed(message)

        elif _SqliteConnectionWrapper._CHECK_RE.search(message):
            raise CheckConstraintFailed(message)

        # other (eg. 'datatype mismatch')
        raise

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
            msg.append('args: {func_args}')
        if kwargs:
            msg.append('kwargs: {func_kwargs}')
        return '\n\t'.join(msg)

    def __log_execute(self, sql, *args, **kwargs):
        """
        Logs the execute call with some "rate-limiting" to prevent very spammy
        calls from flooding the logs

        Note: the limiting is per-process so 2+ processes logging the same query
        will still be logged once per process.
        """
        last_log_time = 0

        try:
            log_times = self.__log_times
        except AttributeError:
            log_times = {}
            self.__log_times = log_times

        try:
            last_log_time = log_times[sql]
        except KeyError:
            pass

        elapsed = time.time() - last_log_time
        # limit how often queries that are called rapidly are logged
        # TODO? config setting for time threshold?
        if elapsed > 60:
            logger.id(logger.debug, self,
                    self.__construct_msg(*args, **kwargs),
                    sql=sql,
                    func_args=args,
                    func_kwargs=kwargs,
            )
            log_times[sql] = time.time()

    def __do_execute(self, func, sql, *args, **kwargs):
        cursor = None
        while not cursor:
            self.__log_execute(sql, *args, **kwargs)
            try:
                cursor = func(sql, *args, **kwargs)

            except sqlite3.OperationalError as e:
                message = _SqliteConnectionWrapper.get_err_msg(err)
                if _SqliteConnectionWrapper._LOCKED_RE.search(message):
                    # a process is taking a long time with its transaction.
                    # this will be spammy if a process holds the lock
                    # indefinitely.
                    logger.id(logger.debug, self,
                            'Database is locked! retrying ...',
                    )

                else:
                    raise

            except sqlite3.IntegrityError as e:
                _SqliteConnectionWrapper.reraise_integrity_error(e)
        return cursor

    def execute(self, sql, *args, **kwargs):
        return self.__do_execute(self.connection.execute, sql, *args, **kwargs)

    def executemany(self, sql, *args, **kwargs):
        return self.__do_execute(
                self.connection.executemany, sql, *args, **kwargs
        )

@add_metaclass(abc.ABCMeta)
class Database(object):
    """
    Data storage handling (replied comments, etc) abstract base class
    """

    PATH_FMT = os.path.join(DATA_ROOT_DIR, 'data', '{0}')

    @staticmethod
    def resolve_path(path):
        if path == ':memory:':
            return path
        return config.resolve_path(path)

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
            logger.id(logger.warn, self,
                    'An error occurred! Rolling back changes ...',
                    exc_info=True,
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
            logger.id(logger.debug, self,
                    'Creating directories \'{dirname}\' ...',
                    dirname=self._dirname,
            )
            try:
                os.makedirs(self._resolved_dirname)
            except OSError as e:
                raise FailedInit(e, e.message)

        logger.id(logger.debug, self,
                'Opening connection to \'{path}\' ...',
                path=self.path,
        )

        try:
            db = sqlite3.connect(self._resolved_path)

        except sqlite3.OperationalError as e:
            raise FailedInit(e, e.message, self._resolved_path)

        else:

            def create_table(table):
                if not isinstance(table, string_types):
                    raise TypeError(
                            'create_table string expected, got {type}'
                            ' (\'{data}\')'.format(
                                type=type(table),
                                data=table,
                            )
                    )
                db.execute('CREATE TABLE IF NOT EXISTS {0}'.format(table))

            try:
                if isinstance(self._create_table_data, string_types):
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

    def __wrapper(self, func, *args, **kwargs):
        """
        Wraps the callback func in a try/except block
        """
        try:
            func(*args, **kwargs)

        except BaseDatabaseException:
            # just re-raise any custom database exceptions thrown
            raise

        except Exception:
            # catch any other errors so the program doesn't terminate
            logger.id(logger.warn, self,
                    '{ME} Failed!'
                    '\n\targs={func_args}'
                    '\n\tkwargs={func_kwargs}',
                    ME=func.__name__.upper(),
                    func_args=args,
                    func_kwargs=kwargs,
                    exc_info=True,
            )

    def insert(self, *args, **kwargs):
        """
        Wrapper to abstract _insert method
        """
        self.__wrapper(self._insert, *args, **kwargs)

    def delete(self, *args, **kwargs):
        """
        Wrapper to overrideable _delete method
        """
        self.__wrapper(self._delete, *args, **kwargs)

    def update(self, *args, **kwargs):
        """
        Wrapper to overrideable _update method
        """
        self.__wrapper(self._update, *args, **kwargs)

    def _initialize_tables(self, db):
        """
        Overrideable method for child classes to do extra initialization of
        tables after creation.

        ** IMPORTANT: self._db should not be referenced within this method **
        Instead, use the db parameter.
        """
        pass

    @abc.abstractproperty
    def _create_table_data(self):
        """
        Table definition string(s) used in __init_db.
        This should return either a string or list of strings which define the
        tables in the database.
        """

    @abc.abstractmethod
    def _insert(self, *args, **kwargs):
        """
        INSERT functionality
        """

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

