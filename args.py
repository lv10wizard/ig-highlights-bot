from __future__ import print_function
import argparse
import os
import re

from six import iteritems
from six.moves import input

from constants import (
        AUTHOR,
        DATA_ROOT_DIR,
)
from src import (
        config,
        reddit,
)
from src.database import (
        BadUsernamesDatabase,
        Database,
        get_class_from_name,
        InstagramDatabase,
        SUBCLASSES,
        SubredditsDatabase,
        UniqueConstraintFailed,
)
from src.util import (
        confirm,
        logger,
        mkdirs,
)


DRY_RUN         = 'dry-run'

SHUTDOWN        = 'shutdown'
BACKUP          = 'backup'
LOAD_BACKUP     = 'load-backup'
ADD_SUBREDDIT   = 'add-subreddit'
RM_SUBREDDIT    = 'rm-subreddit'
ADD_BLACKLIST   = 'add-blacklist'
RM_BLACKLIST    = 'rm-blacklist'
ADD_BAD_USERNAME = 'add-bad-username'
RM_BAD_USERNAME = 'rm-bad-username'
DELETE_DATA     = 'delete-data'
DUMP            = 'dump'
IG_DB           = 'ig-db'
IG_DB_LIKES     = 'ig-db-likes'
IG_DB_COMMENTS  = 'ig-db-comments'
IG_DB_LINKS_RAW = 'ig-db-links-raw'
IG_CHOICES      = 'ig-db-choices'

DATABASE_CHOICES = sorted(list(SUBCLASSES.keys()))
try:
    # disallow InstagramDatabase from --dump choices since they are handled
    # separately
    DATABASE_CHOICES.remove('InstagramDatabase')
except ValueError:
    # database class renamed? this shouldn't happen
    pass

BACKUP_CHOICES = [
        name for name in DATABASE_CHOICES
        # don't bother backing up the ratelimit databases
        if not name.endswith('RateLimitDatabase')
]

igdb_path = Database.format_path(InstagramDatabase.PATH)
resolved_igdb_path = config.resolve_path(igdb_path)
try:
    IG_DB_CHOICES = [
            name for name in os.listdir(resolved_igdb_path)
            if name.endswith('.db')
    ]
except OSError:
    IG_DB_CHOICES = []
    IG_DB_DISPLAY_CHOICES = []
else:
    IG_DB_DISPLAY_CHOICES = sorted([name[:-3] for name in IG_DB_CHOICES])
IG_DB_DISPLAY_CHOICES += ['*']

def to_opt_str(arg_str):
    return arg_str.replace('-', '_')
def to_cmdline(arg_str):
    return arg_str.replace('_', '-')


def shutdown(cfg, do_shutdown=True):
    import sys
    if sys.platform == 'win32':
        from signal import CTRL_C_EVENT as SIGINT
    else:
        from signal import SIGINT

    from src.mixins.proc import get_pid_file

    fail_msg = 'Could not determine bot\'s pid (is the bot running?)'
    bot_pid_file = get_pid_file('IgHighlightsBot')
    if not bot_pid_file:
        logger.info(fail_msg)
        return

    try:
        with open(bot_pid_file, 'r') as fd:
            main_pid = fd.read()
    except (IOError, OSError):
        logger.exception(fail_msg)
        return

    try:
        main_pid = int(main_pid)
    except (TypeError, ValueError):
        msg = [fail_msg, '{path} contents: \'{content}\'']
        logger.exception('\n'.join(msg),
                path=bot_pid_file,
                content=main_pid,
        )
        return

    if confirm('Shutdown bot (pid={0})?'.format(main_pid)):
        logger.info('Shutting down bot ({color_pid}) ...', color_pid=main_pid)

        try:
            os.kill(main_pid, SIGINT)

        except OSError:
            logger.exception('Could not shutdown the bot ({color_pid})!',
                    color_pid=main_pid,
            )

    else:
        logger.info('Leaving the bot alive ({color_pid})', color_pid=main_pid)

def backup(cfg, *databases):
    import sqlite3

    if '*' in databases:
        databases = BACKUP_CHOICES

    for db_name in databases:
        db_class = get_class_from_name(db_name)
        if not db_class:
            continue

        path = Database.format_path(db_class.PATH)
        resolved_path = Database.resolve_path(path)

        if os.path.exists(resolved_path):
            backup_path = Database.format_backup_path(
                    db_class.PATH
            )
            resolved_backup = Database.resolve_path(backup_path)
            mkdirs(os.path.dirname(resolved_backup))

            logger.info('Backing up \'{db_name}\' ({basename})'
                    ' to \'{backup_path}\' ...',
                    db_name=db_name,
                    basename=os.path.basename(path),
                    backup_path=backup_path,
            )

            connection = sqlite3.connect(resolved_path)
            try:
                with open(resolved_backup, 'w') as fd:
                    for line in connection.iterdump():
                        print(line, end=os.linesep, file=fd)

            except (IOError, OSError):
                logger.exception('Failed to backup \'{db_name}\' to SQL'
                        ' text format!',
                        db_name=db_name,
                )

            finally:
                logger.info('Successfully backed up \'{db_name}\' to'
                        ' \'{backup_path}\'!',
                        db_name=db_name,
                        backup_path=backup_path,
                )
                connection.close()

        else:
            logger.info('Cannot backup \'{db_name}\': no database file'
                    ' \'{path}\'',
                    db_name=db_name,
                    path=path,
            )

def _load_backup(db_path, sql_script):
    """
    Loads the database @ db_path with the specified sql_script string.
    ** This will wipe the existing database **

    db_path (str) - the path to the database to load
    sql_script (str) - the SQL script to populate the database with
            (see sqlite3#executescript)

    Returns True if the database is successfully loaded from the script
    """
    import sqlite3

    success = False
    do_load = True
    resolved_path = Database.resolve_path(db_path)

    # keep the database file in case something goes wrong
    # XXX: this isn't 100% safe because it may move the file while it is in
    # an incomplete state, potentially corrupting it. it is however better than
    # simply deleting the database file outright.
    if os.path.exists(resolved_path):
        tmp_path = '{0}.tmp'.format(resolved_path)
        logger.debug('Moving \'{old}\' -> \'{tmp}\'',
                old=db_path,
                tmp=tmp_path,
        )
        try:
            os.rename(resolved_path, tmp_path)
        except OSError:
            logger.exception('Failed to move old database file \'{path}\'!',
                    path=db_path,
            )
            do_load = False

    if do_load:
        mkdirs(os.path.dirname(resolved_path))
        connection = sqlite3.connect(resolved_path)
        try:
            with connection:
                connection.executescript(sql_script)

        except:
            logger.exception('Failed to load \'{db_path}\' from backup!',
                    db_path=db_path,
            )
            logger.info('Reverting ...')
            try:
                # XXX: remove first in case .rename doesn't clobber
                if os.path.exists(resolved_path):
                    os.remove(resolved_path)
                os.rename(tmp_path, resolved_path)
            except OSError:
                logger.exception('Failed to revert \'{tmp}\' -> \'{old}\'!',
                        tmp=tmp_path,
                        old=db_path,
                )

            else:
                logger.debug('Removing \'{tmp}\' ...', tmp=tmp_path)
                try:
                    os.remove(tmp_path)
                except OSError:
                    # littering: load success but the previous database file
                    # wasn't cleaned up properly
                    logger.warn('Failed to remove previous database file'
                            ' \'{tmp}\'',
                            tmp=tmp_path,
                            exc_info=True,
                    )
                success = True

    return success

def load_backup(cfg, *databases):
    import time

    if '*' in databases:
        databases = BACKUP_CHOICES

    logger.info('** Loading from backup will wipe any changes in the'
            ' database **\n')

    for db_name in databases:
        db_class = get_class_from_name(db_name)
        if not db_class:
            continue

        backup_path = Database.format_backup_path(db_class.PATH)
        resolved_backup = Database.resolve_path(backup_path)
        if os.path.exists(resolved_backup):
            try:
                backup_mtime = os.path.getmtime(resolved_backup)
            except (IOError, OSError):
                logger.debug('Failed to stat \'{path}\' (for mtime)',
                        path=backup_path,
                )
                backup_mtime = -1

            confirm_msg = ['Load \'{0}\'?']
            if backup_mtime > 0:
                confirm_msg.append('(backup last modified @ {1})')
            confirm_msg = ' '.join(confirm_msg).format(
                    db_name,
                    time.strftime(
                        '%m/%d, %H:%M:%S', time.localtime(backup_mtime)
                    ),
            )

            if confirm(confirm_msg):
                try:
                    with open(resolved_backup, 'r') as fd:
                        sql = [line for line in fd if line]

                except (IOError, OSError):
                    logger.exception('Failed to read \'{db_name}\' backup'
                            ' ({path})!',
                            db_name=db_name,
                            path=backup_path,
                    )

                else:
                    path = Database.format_path(db_class.PATH)
                    if _load_backup(path, ''.join(sql)):
                        logger.info('Successfully loaded \'{db_name}\''
                                ' ({basename}) from \'{backup_path}\'',
                                db_name=db_name,
                                basename=os.path.basename(path),
                                backup_path=backup_path,
                        )

        else:
            logger.info('Cannot load \'{db_name}\': no backup found ({path})',
                    db_name=db_name,
                    path=backup_path,
            )

def add_subreddit(cfg, *subreddits):
    subreddits_db = SubredditsDatabase(do_seed=False)
    for sub in subreddits:
        _, sub_name = reddit.split_prefixed_name(sub)
        # in case the user passed something like '/u/'
        if sub_name:
            if sub_name not in subreddits_db:
                try:
                    with subreddits_db:
                        subreddits_db.insert(sub_name)
                except UniqueConstraintFailed:
                    # this means there is a bug in __contains__
                    logger.warn('Failed to add \'{sub_name}\' (already added)!',
                            sub_name=reddit.prefix_subreddit(sub_name),
                            exc_info=True,
                    )

                else:
                    logger.info('Successfully added \'{sub_name}\'!',
                            sub_name=reddit.prefix_subreddit(sub_name),
                    )

            else:
                logger.info('Cannot add \'{sub_name}\': already added!',
                        sub_name=sub_name,
                )

def rm_subreddit(cfg, *subreddits):
    subreddits_db = SubredditsDatabase(do_seed=False)
    for sub in subreddits:
        _, sub_name = reddit.split_prefixed_name(sub)
        # in case the user passed something like '/u/'
        if sub_name:
            if sub_name in subreddits_db:
                with subreddits_db:
                    subreddits_db.delete(sub_name)

                logger.info('Successfully removed \'{sub_name}\'!',
                        sub_name=reddit.prefix_subreddit(sub_name),
                )
            else:
                logger.info('Cannot remove \'{sub_name}\': not in database!',
                        sub_name=sub_name,
                )

def add_blacklist(cfg, *names):
    from src.blacklist import Blacklist
    blacklist = Blacklist(cfg)
    for name in names:
        blacklist.add(name)

def rm_blacklist(cfg, *names):
    from src.blacklist import Blacklist
    blacklist = Blacklist(cfg)
    for name in names:
        blacklist.remove(name)

def add_bad_username(cfg, text, fullname, score):
    # TODO? look up submission thing prefix dynamically
    submission_prefix = 't3_'
    if not fullname.startswith(submission_prefix):
        logger.info('Usage: --{add_bad_username_opt} TEXT FULLNAME SCORE',
                add_bad_username_opt=ADD_BAD_USERNAME,
        )
        logger.info('FULLNAME must be a submission fullname (starting with'
                ' {prefix}, not {fullname}): not adding \'{text}\'',
                prefix=submission_prefix,
                fullname=fullname,
                text=text,
        )
        return

    bad_usernames = BadUsernamesDatabase()
    logger.info('Adding \'{color_text}\' ({fullname}, {score}) as a'
            ' bad-username ...',
            color_text=text,
            fullname=fullname,
            score=score,
    )

    try:
        with bad_usernames:
            bad_usernames.insert(text, fullname, score)

    except UniqueConstraintFailed:
        logger.info('\'{color_text}\' already considered a bad-username',
                color_text=text,
        )

    else:
        logger.info('Successfully added \'{color_text}\' as a bad-username!',
                color_text=text,
        )

def rm_bad_username(cfg, *text):
    bad_usernames = BadUsernamesDatabase()
    for t in text:
        if t in bad_usernames:
            logger.info('Removing bad-username: \'{color_text}\' ...',
                    color_text=t,
            )
            with bad_usernames:
                bad_usernames.delete(t)

        else:
            logger.info('\'{color_text}\' was not considered a bad-username!',
                    color_text=t,
            )

def delete_data(cfg, do_delete=True):
    import shutil
    import stat

    if not do_delete:
        return

    # assumption: all data is stored under a single directory
    base_path = DATA_ROOT_DIR
    resolved_path = config.resolve_path(base_path)

    if not os.path.exists(resolved_path):
        logger.info('No program data found in \'{0}\'', resolved_path)
        return

    if confirm('Delete all data in \'{0}\'?'.format(base_path)):
        logger.info('Deleting all data ...')

        def onerr(func, path, exc):
            """
            https://docs.python.org/3/library/shutil.html#rmtree-example
            """
            # qualify the func name so that we get a better sense of which
            # function was called
            funcname = []
            try:
                funcname.append(func.__module__)
            except AttributeError:
                # can this happen?
                pass
            funcname.append(func.__name__)

            logger.debug('An error occured calling {funcname}({path}) !',
                    funcname='.'.join(funcname),
                    path=path,
                    exc_info=True,
            )

            if not os.access(path, os.W_OK):
                logger.debug('Attempting to clear readonly bit ...')
                try:
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                except (IOError, OSError):
                    logger.warn('Could not remove \'{path}\'!',
                            path=path,
                            exc_info=True,
                    )

        shutil.rmtree(resolved_path, onerror=onerr)

    else:
        logger.info('Leaving data as is.')

def do_print_database(path, query=''):
    import sqlite3

    logger.info('Dumping \'{path}\' ...', path=path)

    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row

    try:
        # https://stackoverflow.com/a/305639
        tables = connection.execute(
                'SELECT name FROM sqlite_master WHERE type = \'table\''
        )
    except sqlite3.DatabaseError as e:
        # eg. not a database
        logger.exception('Could not lookup tables in \'{path}\'',
                path=path,
        )
    else:
        print('{0}:'.format(os.path.basename(path)), end='\n\n')
        # https://stackoverflow.com/a/13335514
        #    [('foo',), ('bar',), ('baz',)]
        # -> ('foo', 'bar', 'baz')
        tables = [name[0] for name in tables]
        cursors = {
                name: connection.execute(
                    'SELECT * FROM {0} {1}'.format(name, query)
                )
                for name in tables
        }

        sep = ' | '
        horiz_sep = '-' * 72
        end = 'number of rows:'
        for name in cursors:
            print(horiz_sep)
            print('table \'{0}\':'.format(name))
            print(horiz_sep)
            cur = cursors[name]
            num = 0
            keys = []
            padding = {}
            for row in cur:
                if not keys:
                    keys = row.keys()
                    columns = []
                    for k in keys:
                        # XXX: assume the first row is emblematic of the width
                        # of each column to avoid reading the entire database
                        # into memory (this may mean that some rows are not
                        # formatted correctly)
                        padding[k] = max(len(str(row[k])), len(k))
                        columns.append('{0:^{1}}'.format(k, padding[k]))
                    # print out the columns
                    print(*columns, sep=sep)
                    print(horiz_sep)
                # print out each row
                row_str = [
                        '{0:<{1}}'.format(str(row[k]), padding[k])
                        for k in keys
                ]
                print(*row_str, sep=sep)
                num += 1

            end_out_len = len(end) + len(str(num)) + 1 # +1 for space
            end_sep = ' ' + horiz_sep[end_out_len + 1:] # +1 for space
            print(end, num, end=end_sep + '\n\n')

def print_database(cfg, *databases):
    if '*' in databases:
        # dump all databases
        databases = DATABASE_CHOICES

    for db_name in databases:
        if db_name == 'InstagramDatabase':
            logger.info('Please use --{opt} to dump individual instagram'
                    ' databases',
                    opt=IG_DB,
            )
            continue

        db_class = get_class_from_name(db_name)
        if not db_class:
            continue

        path = Database.format_path(db_class.PATH)
        resolved_path = Database.resolve_path(path)
        if os.path.exists(resolved_path):
            do_print_database(resolved_path)

        else:
            logger.info('No database file: \'{path}\'', path=path)

def print_instagram_database_wrapper(callback, order, *user_databases):
    if '*' in user_databases:
        # dump all instagram databases
        user_databases = IG_DB_CHOICES

    orig_order = order
    for user_db in user_databases:
        if not user_db.endswith('.db'):
            user_db = '{0}.db'.format(user_db)

        path = os.path.join(resolved_igdb_path, user_db)
        if os.path.exists(path):
            if not orig_order:
                # use the default order if none was specified
                igdb = InstagramDatabase(path)
                if igdb.size() == 0:
                    igdb.close()
                    logger.info('Removing \'{path}\': empty database ...',
                            path=path,
                    )
                    try:
                        os.remove(path)
                    except (IOError, OSError):
                        logger.exception('Failed to remove \'{path}\'!',
                                path=path,
                        )

                    continue
                order = 'ORDER BY {0}'.format(igdb.order_string)

            logger.debug(order)
            callback(path, order)

        else:
            path_raw = os.path.join(InstagramDatabase.PATH, user_db)
            logger.info('No instagram data for user: \'{user}\'',
                    user=re.sub(r'[.]db$', '', user_db),
            )

def print_instagram_database(cfg, order, *user_databases):
    print_instagram_database_wrapper(do_print_database, order, *user_databases)

def print_instagram_database_links(cfg, order, *user_databases):
    def do_print_links(path, order):
        import sqlite3
        from src.instagram.constants import MEDIA_LINK_FMT

        if os.path.exists(path):
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            cursor = db.execute('SELECT code FROM cache {0}'.format(order))
            for row in cursor:
                print(MEDIA_LINK_FMT.format(row['code']))

    print_instagram_database_wrapper(do_print_links, order, *user_databases)

def print_igdb_choices(cfg, do_print=True):
    if not do_print:
        return

    print('--{0} choices:'.format(IG_DB))
    line = []
    sep = ', '
    first_char = None
    for c in IG_DB_DISPLAY_CHOICES:
        formatted_line = sep.join(line)
        c_first = c[0].lower()
        if first_char != c_first:
            # separate the choices by the first letter
            end = ''
            if formatted_line:
                end = sep
            end += '\n\n'
            print(formatted_line, end=end)
            first_char = c_first
            line = [c]

        # '..., <c>, ' => 2 * len(sep)
        elif len(formatted_line) + 2*len(sep) + len(c) >= 80:
            print(formatted_line, end=sep+'\n')
            line = [c]

        else:
            line.append(c)

    if line:
        # print the trailing database choices
        print(sep.join(line))

def handle(cfg, args):
    handlers = {
            SHUTDOWN: shutdown,
            BACKUP: backup,
            LOAD_BACKUP: load_backup,
            ADD_SUBREDDIT: add_subreddit,
            RM_SUBREDDIT: rm_subreddit,
            ADD_BLACKLIST: add_blacklist,
            RM_BLACKLIST: rm_blacklist,
            ADD_BAD_USERNAME: add_bad_username,
            RM_BAD_USERNAME: rm_bad_username,
            DELETE_DATA: delete_data,
            DUMP: print_database,
            IG_DB: print_instagram_database,
            IG_DB_LIKES: print_instagram_database,
            IG_DB_COMMENTS: print_instagram_database,
            IG_DB_LINKS_RAW: print_instagram_database_links,
            IG_CHOICES: print_igdb_choices,
    }
    order = {
            IG_DB: None,
            IG_DB_LIKES: 'ORDER BY num_likes DESC',
            IG_DB_COMMENTS: 'ORDER BY num_comments DESC',
            IG_DB_LINKS_RAW: None,
    }

    had_handleable_opt = False
    for opt, opt_val in iteritems(args):
        opt_key = to_cmdline(opt)
        # XXX: options should evaluate to true if they are to be handled
        if opt_key in handlers and bool(opt_val):
            had_handleable_opt = True
            try:
                handler_func = handlers[opt_key]
            except KeyError as e:
                logger.exception('No option handler defined for \'{opt}\'!',
                        opt=opt,
                )
            else:
                try:
                    if opt_key in order:
                        handler_func(cfg, order[opt_key], *opt_val)
                    else:
                        handler_func(cfg, *opt_val)
                except TypeError:
                    # opt_val not iterable
                    handler_func(cfg, opt_val)

    return had_handleable_opt

def parse():
    parser = argparse.ArgumentParser(
            description='Instagram Highlights Bot, a reddit bot that will reply'
            ' to comments linking to instagram accounts with their most popular'
            ' media.'
    )

    parser.add_argument('-c', '--config', metavar='PATH',
            help='Custom config path; default: {0}'.format(config.Config.PATH),
    )
    parser.add_argument('-d', '--{0}'.format(DRY_RUN), action='store_true',
            help='Runs the bot normally but disables it from replying to'
            ' comments and posts. This mode is intended as a sort of "live"'
            ' test.'
    )

    parser.add_argument('-P', '--logging-path', metavar='PATH',
            help='Set the root directory to save logs to (this overrides the'
            ' config setting).',
    )
    parser.add_argument('-L', '--logging-level',
            choices=[
                logger.DEBUG, 'DEBUG',
                logger.INFO, 'INFO',
                logger.WARNING, 'WARNING',
                logger.ERROR, 'ERROR',
                logger.CRITICAL, 'CRITICAL',
            ],
            help='Set the logging level (this overrides the config setting).',
    )
    parser.add_argument('-N', '--logging-no-color', action='store_true',
            help='Turn off logging colors (this overrides the config setting).',
    )

    parser.add_argument('--{0}'.format(SHUTDOWN), action='store_true',
            help='Kills the bot process and all sub-processes.',
    )

    parser.add_argument('--{0}'.format(ADD_SUBREDDIT),
            metavar='SUBREDDIT', nargs='+',
            help='Add subreddit(s) to the comment stream (these are subreddits'
            ' that the bot crawls).',
    )
    parser.add_argument('--{0}'.format(RM_SUBREDDIT),
            metavar='SUBREDDIT', nargs='+',
            help='Remove subreddit(s) from the comment stream (the bot will'
            ' no longer crawl these subreddits but will still make replies if'
            ' summoned).',
    )

    user_example = 'user(s) (eg. \'{0}{1}\')'.format(reddit.PREFIX_USER, AUTHOR)
    sub_example = 'subreddit(s) (eg. \'{0}{1}\')'.format(
            reddit.PREFIX_SUBREDDIT, 'history'
    )
    note = (
            'Note: user profiles are specified as \'{0}u_<username>\''
            ' (eg. \'{0}u_{1}\')'.format(reddit.PREFIX_SUBREDDIT, AUTHOR)
    )
    parser.add_argument('--{0}'.format(ADD_BLACKLIST),
            metavar='NAME', nargs='+',
            help='Blacklist {user} or {sub} so that the bot no longer replies'
            ' to those user(s) or to comments/posts in those subreddit(s).'
            ' {note}.'.format(
                user=user_example,
                sub=sub_example,
                note=note,
            ),
    )
    parser.add_argument('--{0}'.format(RM_BLACKLIST),
            metavar='NAME', nargs='+',
            help='Remove {user} or {sub} from the blacklist so that the bot can'
            ' reply to those user(s) or comments/posts in those subreddit(s).'
            ' {note}.'.format(
                user=user_example,
                sub=sub_example,
                note=note,
            )
    )

    parser.add_argument('--{0}'.format(ADD_BAD_USERNAME),
            metavar='STRING', nargs=3,
            help='Adds a string to the bad-usernames database so that it will'
            ' not be matched in the future as a potential username.'
            ' Usage: --{0} bad_username submission_fullname score. The first'
            ' argument should be the string that the bot should ignore in the'
            ' future. The second argument should be the fullname of the'
            ' submission containing the username. The third should be'
            ' the score of the deleted bot comment.'.format(ADD_BAD_USERNAME),
    )
    parser.add_argument('--{0}'.format(RM_BAD_USERNAME),
            metavar='STRING', nargs='+',
            help='Removes the string(s) from the bad-usernames database so that'
            ' they can be matched in the future as potential instagram'
            ' usernames again.'
    )

    parser.add_argument('--{0}'.format(DELETE_DATA), action='store_true',
            help='Remove all data saved by the program.'
            ' This will ask for confirmation.',
    )

    database_choices = DATABASE_CHOICES + ['*']
    backup_choices = BACKUP_CHOICES + ['*']
    parser.add_argument('--{0}'.format(DUMP),
            metavar='NAME', nargs='+', choices=database_choices,
            help='Dump the specified database(s) to stdout.'
            ' Choices: {0}'.format(database_choices),
    )
    parser.add_argument('--{0}'.format(BACKUP),
            metavar='NAME', nargs='+', choices=backup_choices,
            help='Backup the specified database(s) to an SQL text format.'
            ' Backups are stored in \'{0}\'. Choices: {1}.'.format(
                Database.BACKUPS_PATH_ROOT, backup_choices,
            ),
    )
    parser.add_argument('--{0}'.format(LOAD_BACKUP),
            metavar='NAME', nargs='+', choices=backup_choices,
            help='Load the specified database(s) from'
            ' its last --{0} dump. **This will cause any changes since the'
            ' last --{0} to be lost**'
            ' (will ask for confirmation). See --{0} for choices.'.format(
                BACKUP,
            ),
    )

    ig_actual_choices = IG_DB_CHOICES + IG_DB_DISPLAY_CHOICES
    parser.add_argument('--{0}'.format(IG_DB),
            metavar='NAME', nargs='+',
            choices=ig_actual_choices,
            help='Dump the specified instagram user databases to stdout.'
            ' See --{0} for choices.'.format(IG_CHOICES),
    )
    parser.add_argument('--{0}'.format(IG_DB_LIKES), metavar='NAME',
            nargs='+', choices=ig_actual_choices,
            help='Dump the specified instagram user databases to stdout'
            ' sorted by most likes -> least likes.'
            ' See --{0} for choices.'.format(IG_CHOICES),
    )
    parser.add_argument('--{0}'.format(IG_DB_COMMENTS), metavar='NAME',
            nargs='+', choices=ig_actual_choices,
            help='Dump the specified instagram user databases to stdout'
            ' sorted by most comments -> least comments.'
            ' See --{0} for choices.'.format(IG_CHOICES),
    )
    parser.add_argument('--{0}'.format(IG_DB_LINKS_RAW), metavar='NAME',
            nargs='+', choices=ig_actual_choices,
            help='Dump the specified instagram user databases\' links to'
            ' stdout. See --{0} for choices.'.format(IG_CHOICES),
    )
    parser.add_argument('-I', '--{0}'.format(IG_CHOICES),
            action='store_true',
            help='List valid --{0} choices.'.format(IG_DB),
    )

    return vars(parser.parse_args())


__all__ = [
        'handle',
        'parse',
]

