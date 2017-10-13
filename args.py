from __future__ import print_function
import argparse
import os
import re

from six import iteritems
from six.moves import input

from constants import (
        __DEBUG__,
        AUTHOR,
)
from src import (
        config,
        database,
        reddit,
)
from src.util import logger


SHUTDOWN        = 'shutdown'
ADD_SUBREDDIT   = 'add-subreddit'
RM_SUBREDDIT    = 'rm-subreddit'
ADD_BLACKLIST   = 'add-blacklist'
RM_BLACKLIST    = 'rm-blacklist'
DELETE_DATA     = 'delete-data'
DUMP            = 'dump'
IG_DB           = 'ig-db'
IG_DB_LIKES     = 'ig-db-likes'
IG_DB_COMMENTS  = 'ig-db-comments'

DUMP_CHOICES = sorted(list(database.SUBCLASSES.keys()))
try:
    # disallow InstagramDatabase from --dump choices since they are handled
    # separately
    DUMP_CHOICES.remove('InstagramDatabase')
except ValueError:
    # database class renamed? this shouldn't happen
    pass

resolved_igdb_path = config.resolve_path(database.InstagramDatabase.PATH)
try:
    IG_DB_CHOICES = sorted([
            name for name in os.listdir(resolved_igdb_path)
            if name.endswith('.db')
    ])
except OSError:
    IG_DB_CHOICES = []

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

    confirm = input('Shutdown bot (pid={0})? [Y/n] '.format(main_pid))
    if confirm == 'Y':
        logger.info('Shutting down bot ({color_pid}) ...', color_pid=main_pid)

        try:
            os.kill(main_pid, SIGINT)

        except OSError:
            logger.exception('Could not shutdown the bot ({color_pid})!',
                    color_pid=main_pid,
            )

    else:
        logger.info('Leaving the bot alive ({color_pid})', color_pid=main_pid)

def add_subreddit(cfg, *subreddits):
    subreddits_db = database.SubredditsDatabase(do_seed=False)
    for sub in subreddits:
        _, sub_name = reddit.split_prefixed_name(sub)
        # in case the user passed something like '/u/'
        if sub_name:
            if sub_name not in subreddits_db:
                try:
                    with subreddits_db:
                        subreddits_db.insert(sub_name)
                except database.UniqueConstraintFailed:
                    # this means there is a bug in __contains__
                    logger.warn('Failed to add \'{sub_name}\' (already added)!',
                            sub_name=reddit.prefix_subreddit(sub_name),
                            exc_info=True,
                    )

            else:
                logger.debug('Cannot add \'{sub_name}\': already added!',
                        sub_name=sub_name,
                )

def rm_subreddit(cfg, *subreddits):
    subreddits_db = database.SubredditsDatabase(do_seed=False)
    for sub in subreddits:
        _, sub_name = reddit.split_prefixed_name(sub)
        # in case the user passed something like '/u/'
        if sub_name:
            if sub_name in subreddits_db:
                with subreddits_db:
                    subreddits_db.delete(sub_name)
            else:
                logger.debug('Cannot remove \'{sub_name}\': not in database!',
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

def delete_data(cfg, do_delete=True):
    import shutil
    import stat

    if not do_delete:
        return

    # assumption: all data is stored under a single directory
    base_path = os.path.dirname(database.Database.PATH_FMT)
    resolved_path = config.resolve_path(base_path)

    if not os.path.exists(resolved_path):
        logger.info('No program data found in \'{0}\'', resolved_path)
        return

    confirm = input('Delete all data in \'{0}\'? [Y/n] '.format(base_path))
    # only accept 'Y' as confirmation
    if confirm == 'Y':
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
        databases = DUMP_CHOICES

    for db_name in databases:
        if db_name == 'InstagramDatabase':
            logger.info('Please use --{opt} to dump individual instagram'
                    ' databases',
                    opt=IG_DB,
            )
            continue

        try:
            db_class = database.SUBCLASSES[db_name]
        except KeyError:
            logger.info('Unrecognized database: \'{db_name}\'',
                    db_name=db_name,
            )
        else:
            resolved_path = database.Database.resolve_path(db_class.PATH)
            if os.path.exists(resolved_path):
                do_print_database(resolved_path)

def print_instagram_database(cfg, order, *user_databases):
    if '*' in user_databases:
        # dump all instagram databases
        user_databases = IG_DB_CHOICES

    for user_db in user_databases:
        path = os.path.join(resolved_igdb_path, user_db)
        if os.path.exists(path):
            if not order:
                # use the default order if none was specified
                igdb = database.InstagramDatabase(path)
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
            do_print_database(path, order)

        else:
            path_raw = os.path.join(database.InstagramDatabase.PATH, user_db)
            logger.info('No instagram data for user: \'{user}\'',
                    user=re.sub(r'[.]db$', '', user_db),
            )

def handle(cfg, args):
    def to_opt_str(arg_str):
        return arg_str.replace('-', '_')
    def to_cmdline(arg_str):
        return arg_str.replace('_', '-')

    handlers = {
            SHUTDOWN: shutdown,
            ADD_SUBREDDIT: add_subreddit,
            RM_SUBREDDIT: rm_subreddit,
            ADD_BLACKLIST: add_blacklist,
            RM_BLACKLIST: rm_blacklist,
            DELETE_DATA: delete_data,
            DUMP: print_database,
            IG_DB: print_instagram_database,
            IG_DB_LIKES: print_instagram_database,
            IG_DB_COMMENTS: print_instagram_database,
    }
    order = {
            IG_DB: None,
            IG_DB_LIKES: 'ORDER BY num_likes DESC',
            IG_DB_COMMENTS: 'ORDER BY num_comments DESC',
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
    parser.add_argument('-d', '--dry-run', action='store_true',
            help='Runs the bot normally but disables it from replying to'
            ' comments',
    )

    parser.add_argument('-P', '--logging-path', metavar='PATH',
            help='Set the root directory to save logs to (this overrides the'
            ' config setting)',
    )
    parser.add_argument('-L', '--logging-level',
            choices=[
                logger.DEBUG, 'DEBUG',
                logger.INFO, 'INFO',
                logger.WARNING, 'WARNING',
                logger.ERROR, 'ERROR',
                logger.CRITICAL, 'CRITICAL',
            ],
            help='Set the logging level (this overrides the config setting)',
    )
    parser.add_argument('-N', '--logging-no-color', action='store_true',
            help='Turn off logging colors (this overrides the config setting)',
    )

    parser.add_argument('--{0}'.format(SHUTDOWN), action='store_true',
            help='Kills the bot process and all sub-processes.',
    )

    parser.add_argument('--{0}'.format(ADD_SUBREDDIT),
            metavar='SUBREDDIT', nargs='+',
            help='Add subreddit(s) to the comment stream (these are subreddits'
            ' that the bot crawls by default)',
    )
    parser.add_argument('--{0}'.format(RM_SUBREDDIT),
            metavar='SUBREDDIT', nargs='+',
            help='Remove subreddit(s) from the comment stream (the bot will'
            ' no longer crawl these subreddits but will still make replies if'
            ' summoned)',
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
            ' {note}'.format(
                user=user_example,
                sub=sub_example,
                note=note,
            ),
    )
    parser.add_argument('--{0}'.format(RM_BLACKLIST),
            metavar='NAME', nargs='+',
            help='Remove {user} or {sub} from the blacklist so that the bot can'
            ' reply to those user(s) or comments/posts in those subreddit(s).'
            ' {note}'.format(
                user=user_example,
                sub=sub_example,
                note=note,
            )
    )

    parser.add_argument('--{0}'.format(DELETE_DATA), action='store_true',
            help='Remove all data saved by the program',
    )

    dump_choices = DUMP_CHOICES + ['*']
    parser.add_argument('--{0}'.format(DUMP),
            metavar='NAME', nargs='+', choices=dump_choices,
            help='Dump the specified databases to stdout. Choices: {0}'.format(
                dump_choices
            ),
    )

    ig_choices = IG_DB_CHOICES + ['*']
    parser.add_argument('--{0}'.format(IG_DB),
            metavar='NAME', nargs='+', choices=ig_choices,
            help='Dump the specified instagram user databases to stdout.'
            ' Choices: {0}'.format(ig_choices),
    )
    parser.add_argument('--{0}'.format(IG_DB_LIKES), metavar='NAME',
            nargs='+', choices=ig_choices,
            help='Dump the specified instagram user databases to stdout'
            ' sorted by most likes -> least likes.'
            ' See --{0} for choices'.format(IG_DB),
    )
    parser.add_argument('--{0}'.format(IG_DB_COMMENTS), metavar='NAME',
            nargs='+', choices=ig_choices,
            help='Dump the specified instagram user databases to stdout'
            ' sorted by most comments -> least comments.'
            ' See --{0} for choices'.format(IG_DB),
    )

    args = vars(parser.parse_args())
    if __DEBUG__:
        logger.debug('args:\n{pprint}', pprint=args)
    return args


__all__ = [
        'handle',
        'parse',
]

