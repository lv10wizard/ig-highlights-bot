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

class FailedVerificationCheck(BaseDatabaseException): pass

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
    def reraise_integrity_error(err):
        message = Database.get_err_msg(err)
        if _SqliteConnectionWrapper._UNIQUE_RE.search(message):
            raise UniqueConstraintFailed(message)

        elif _SqliteConnectionWrapper._NOTNULL_RE.search(message):
            raise NotNullConstraintFailed(message)

        elif _SqliteConnectionWrapper._CHECK_RE.search(message):
            raise CheckConstraintFailed(message)

        # other (eg. 'datatype mismatch')
        raise

    def __init__(self, connection, parent):
        self.connection = connection
        self.parent = parent

    def __str__(self):
        return str(self.parent)

    def __enter__(self):
        return self.connection

    def __exit__(self, *args, **kwargs):
        self.connection.__exit__(*args, **kwargs)

    def __getattr__(self, attr):
        return getattr(self.connection, attr)

    def __construct_msg(self, sql, *args, **kwargs):
        msg = ['{0}'.format(sql)]
        if args:
            msg.append('args: {func_args}')
        if kwargs:
            msg.append('kwargs: {func_kwargs}')
        return '\n\t'.join(msg)

    def __do_execute(self, func, sql, *args, **kwargs):
        cursor = None
        while not cursor:
            self.parent.do_log(logger.debug,
                    self.__construct_msg(sql, *args, **kwargs),
                    min_threshold_=30,
                    func_args=args,
                    func_kwargs=kwargs,
            )

            try:
                cursor = func(sql, *args, **kwargs)

            except sqlite3.OperationalError as e:
                message = Database.get_err_msg(e)
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

    TABLENAME_RE = re.compile(r'^(\w+)\s*[(]')
    COLUMN_RE = re.compile(r'\s*(\w+).+?')

    @staticmethod
    def resolve_path(path):
        if path == ':memory:':
            return path
        return config.resolve_path(path)

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

    def do_log(
            self, logger_func, msg_, min_threshold_=60, force_=False,
            *args_, **kwargs_
    ):
        """
        This method time-gates logging calls to prevent flooding the logs if
        min_threshold_ > 0.

        logger_func (function) - the logger method to call (eg. logger.debug)
        msg_ (str) - the format message to pass to the logger
                Note: this string is used as a key to gauge the elapsed interval
                of the last logging output. so if the msg_ string changes
                dynamically, then logging may still be spammed.
        min_threshold_ (int, float; optional) - the minimum elapsed time before
                the given msg_ can be logged again
        force_ (bool; optional) - whether logging should be output regardless
                of the elapsed time since the last output of msg_. this has no
                effect if min_threshold_ <= 0 (logging is always output if
                min_threshold_ <= 0).
        """
        did_log = False

        last_log_time = 0
        # don't bother checking/creating caches if we're just going to log
        # anyway
        if min_threshold_ > 0 or force_:
            try:
                log_times = self.__last_log_time
            except AttributeError:
                log_times = {}
                self.__last_log_time = log_times

            try:
                last_log_time = log_times[msg_]
            except KeyError:
                pass

        elapsed = time.time() - last_log_time
        # limit how often messages are logged
        # TODO? config setting for time threshold?
        if elapsed > min_threshold_ or force_:
            logger.id(logger_func, self, msg_, *args_, **kwargs_)
            if min_threshold_ > 0:
                log_times[msg_] = time.time()
            did_log = True

        return did_log

    @property
    def _db(self):
        """
        Memoized database connection instance
        """
        db = None
        try:
            db = self.__the_connection

        except AttributeError:
            db = self.__init_db()
            if db is None:
                # the database was outdated; re-initialize it
                db = self.__init_db()

            self.__the_connection = db

        return db

    def __verify_db(self, db, tbl_defn):
        """
        Checks if the table definition has changed.
        This may happen if a database's wrapper code has changed since it was
        first created.

        Note: this does not verify column types.

        Returns True if the database matches the definition or the existing
                    extraneous columns were removed
                or False if the database table is missing columns that exist in
                    the definition
        """
        name_match = Database.TABLENAME_RE.search(tbl_defn)
        if not name_match:
            # either TABLENAME_RE needs updating or unexpected
            # table definition
            raise FailedVerificationCheck(
                    'Failed to determine table name from'
                    ' \'{0}\''.format(tbl_defn)
            )
        name = name_match.group(1)

        columns = set()
        col_start = tbl_defn.find('(')
        col_end = tbl_defn.rfind(')')
        for col in tbl_defn[col_start+1 : col_end].split(','):
            match = Database.COLUMN_RE.search(col)
            if not match:
                # either COLUMN_RE needs updating or unexpected
                # column definition
                raise FailedVerificationCheck(
                        'Failed to determine column name from'
                        ' \'{0}\''.format(col)
                )
            columns.add(match.group(1))

        # get actual column names
        # https://stackoverflow.com/a/20643403
        info = db.execute('PRAGMA table_info(\'{0}\')'.format(name)).fetchall()
        existing_columns = set(row['name'] for row in info)

        logger.id(logger.debug, self,
                'Verifying integrity of table \'{tblname}\':'
                '\n\tdefined columns: {color_def}'
                '\n\tactual columns:  {color_actual}',
                tblname=name,
                color_def=columns,
                color_actual=existing_columns,
        )

        extra_columns = existing_columns - columns
        if extra_columns:
            logger.id(logger.info, self,
                    'Table \'{tblname}\' has extra columns: {color}',
                    tblname=name,
                    color=extra_columns,
            )
            logger.id(logger.debug, self, 'Dropping the extra columns ...')
            tmp_name = '__TMP__{0}__TMP__'.format(name)
            # drop the extra columns
            # https://stackoverflow.com/a/4253879
            db.execute('ALTER TABLE {0} RENAME TO {1}'.format(name, tmp_name))
            db.execute('CREATE TABLE {0}'.format(tbl_defn))
            # copy the data into the new table
            db.execute('INSERT INTO {0}({2}) SELECT {2} FROM {1}'.format(
                name, tmp_name, ', '.join(columns)
            ))
            db.execute('DROP TABLE {0}'.format(tmp_name))

        missing_columns = columns - existing_columns
        if missing_columns:
            # the entire table should be dropped in this situation in case one
            # or more new (missing) columns are integral to the database's
            # behavior
            logger.id(logger.info, self,
                    'Table \'{tblname}\' is missing columns: {color}',
                    tblname=name,
                    color=missing_columns,
            )

        return not bool(missing_columns)

    def __init_db(self):
        """
        Initializes the database connection.

        Returns db (_SqliteConnectionWrapper) if initialization succeeds
                or None if an existing database is outdated
        """
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
                raise FailedInit(e, Database.get_err_msg(e))

        logger.id(logger.debug, self,
                'Opening connection to \'{path}\' ...',
                path=self.path,
        )

        do_integrity_check = os.path.exists(self._resolved_path)

        try:
            db = sqlite3.connect(self._resolved_path)

        except sqlite3.OperationalError as e:
            raise FailedInit(e, Database.get_err_msg(e), self._resolved_path)

        else:
            # https://docs.python.org/2/library/sqlite3.html#row-objects
            db.row_factory = sqlite3.Row
            db = _SqliteConnectionWrapper(db, self)

            def initialize_table(table):
                success = True
                if not isinstance(table, string_types):
                    raise TypeError(
                            'initialize_table string expected, got {type}'
                            ' (\'{data}\')'.format(
                                type=type(table),
                                data=table,
                            )
                    )
                db.execute('CREATE TABLE IF NOT EXISTS {0}'.format(table))

                if do_integrity_check:
                    success = self.__verify_db(db, table)
                return success

            try:
                verified = True
                if isinstance(self._create_table_data, string_types):
                    verified = initialize_table(self._create_table_data)
                elif isinstance(self._create_table_data, (list, tuple)):
                    for table in self._create_table_data:
                        verified = initialize_table(table) and verified

                else:
                    # programmer error
                    raise TypeError(
                            'Unhandled _create_table_data'
                            ' type=\'{type}\''.format(
                                type=type(self._create_table_data)
                            )
                    )

                if not verified:
                    # existing database does not match table definition(s)
                    db.close()
                    db = None

                    logger.id(logger.info, self,
                            'Outdated database detected:'
                            ' removing \'{path}\' ...',
                            path=self.path,
                    )

                    # XXX: this is a heavy-handed, lazy solution which will
                    # cause data loss. if the database was missing columns, then
                    # data loss probably shouldn't be a huge issue.
                    try:
                        os.remove(self._resolved_path)
                    except (IOError, OSError):
                        # database is probably in use by another process.
                        # terminate this process if we couldn't remove it so
                        # that we're not trying to work with an outdated
                        # database.
                        logger.id(logger.critical, self,
                                'Could not remove outdated database'
                                ' @ \'{path}\'!',
                                path=self.path,
                                exc_info=True,
                        )
                        raise

                else:
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
                raise FailedInit(e, Database.get_err_msg(e))
        return db

    def commit(self):
        self._db.commit()

    def rollback(self):
        self._db.rollback()

    def close(self):
        """
        Closes the database connection
        """
        try:
            self.__the_connection
        except AttributeError:
            # don't create a new connection if none exists
            pass
        else:
            self.__the_connection.close()

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
                    '\n\targs={pprint_func_args}'
                    '\n\tkwargs={pprint_func_kwargs}',
                    ME=func.__name__.upper(),
                    pprint_func_args=args,
                    pprint_func_kwargs=kwargs,
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

