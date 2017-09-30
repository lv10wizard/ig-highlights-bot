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


ADD_SUBREDDIT = 'add-subreddit'
RM_SUBREDDIT  = 'rm-subreddit'
ADD_BLACKLIST = 'add-blacklist'
RM_BLACKLIST  = 'rm-blacklist'
DELETE_DATA   = 'delete-data'
DUMP          = 'dump'
IG_DB         = 'ig-db'

def add_subreddit(cfg, *subreddits):
    subreddits = database.SubredditsDatabase(do_seed=False)
    for sub in subreddits:
        _, sub_name = reddit.split_prefixed_name(sub)
        # in case the user passed something like '/u/'
        if sub_name:
            if sub_name not in subreddits:
                try:
                    with subreddits:
                        subreddits.insert(sub_name)
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
    subreddits = database.SubredditsDatabase(do_seed=False)
    for sub in subreddits:
        _, sub_name = reddit.split_prefixed_name(sub)
        # in case the user passed something like '/u/'
        if sub_name:
            if sub_name in subreddits:
                with subreddits:
                    subreddits.delete(sub_name)
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

def print_instagram_database(cfg, *user_databases):
    resolved_igdb_path = config.resolve_path(database.InstagramDatabase.PATH)
    for user_db in user_databases:
        path = os.path.join(resolved_igdb_path, user_db)
        if os.path.exists(path):
            do_print_database(path, 'ORDER BY num_likes DESC')

        else:
            path_raw = os.path.join(database.InstagramDatabase.PATH, user_db)
            logger.info('No instagram data for user: \'{user}\'',
                    user=re.sub(r'[.]db$', '', user_db),
            )

def handle(cfg, args):
    def convert(arg_str):
        return arg_str.replace('-', '_')

    ignore_keys = [
            'config',
            'logging_path',
            'logging_level',
            'logging_no_color',
    ]
    handlers = {
            convert(ADD_SUBREDDIT): add_subreddit,
            convert(RM_SUBREDDIT): rm_subreddit,
            convert(ADD_BLACKLIST): add_blacklist,
            convert(RM_BLACKLIST): rm_blacklist,
            convert(DELETE_DATA): delete_data,
            convert(DUMP): print_database,
            convert(IG_DB): print_instagram_database,
    }

    had_handleable_opt = False
    for opt, opt_val in iteritems(args):
        # XXX: options should evaluate to true if they are to be handled
        if opt not in ignore_keys and bool(opt_val):
            had_handleable_opt = True
            opt_key = convert(opt)
            try:
                handler_func = handlers[opt_key]
            except KeyError as e:
                logger.exception('No option handler defined for \'{opt}\'!',
                        opt=opt,
                )
            else:
                try:
                    handler_func(cfg, *opt_val)
                except TypeError:
                    # opt_val not iterable
                    handler_func(cfg, opt_val)

    return had_handleable_opt

def parse():
    parser = argparse.ArgumentParser(
            description='Instagram Highlights Bot, a reddit bot that will reply'
            ' to comments linking to instagram accounts with their top-liked'
            ' media.'
    )

    parser.add_argument('-c', '--config', metavar='PATH',
            help='Custom config path; default: {0}'.format(config.Config.PATH),
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

    parser.add_argument('--{0}'.format(DUMP),
            metavar='NAME', nargs='+', choices=list(database.SUBCLASSES.keys()),
            help='Dump the specified databases to stdout',
    )

    resolved_igdb_path = config.resolve_path(database.InstagramDatabase.PATH)
    try:
        ig_choices = [
                name for name in os.listdir(resolved_igdb_path)
                if name.endswith('.db')
        ]
    except OSError:
        ig_choices = []
    parser.add_argument('--{0}'.format(IG_DB),
            metavar='NAME', nargs='+', choices=ig_choices,
            help='Dump the specified instagram user databases to stdout',
    )

    args = vars(parser.parse_args())
    if __DEBUG__:
        logger.debug('args:\n{pprint}', pprint=args)
    return args


__all__ = [
        'handle',
        'parse',
]

