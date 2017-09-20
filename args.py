from __future__ import print_function
import argparse
import os
from pprint import pformat

from constants import (
        __DEBUG__,
        AUTHOR,
)
from src import (
        config,
        reddit,
)
from src.util import logger


ADD_SUBREDDIT = 'add-subreddit'
RM_SUBREDDIT  = 'rm-subreddit'
ADD_BLACKLIST = 'add-blacklist'
RM_BLACKLIST  = 'rm-blacklist'
DUMP          = 'dump'

def add_subreddit(cfg, *subreddits):
    from src.database import SubredditsDatabase
    subreddits = SubredditsDatabase(cfg.subreddits_db_path, do_seed=False)
    for sub in subreddits:
        _, sub_name = reddit.split_prefixed_name(sub)
        # in case the user passed something like '/u/'
        if sub_name:
            if sub_name not in subreddits:
                with subreddits:
                    subreddits.insert(sub_name)
            else:
                logger.debug('Cannot add \'{sub_name}\': already added!',
                        sub_name=sub_name,
                )

def rm_subreddit(cfg, *subreddits):
    from src.database import SubredditsDatabase
    subreddits = SubredditsDatabase(cfg.subreddits_db_path, do_seed=False)
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

def do_print_database(path):
    import sqlite3

    connection = sqlite3.connect(path)
    connection.row_factory = Row
    try:
        # https://stackoverflow.com/a/305639
        tables = connection.execute(
                'SELECT name FROM sqlite_master WHERE name = \'table\''
        )
    except sqlite3.DatabaseError as e:
        # eg. not a database
        logger.exception('Could not lookup tables in \'{path}\'',
                path=path,
                exc_info=e,
        )
    else:
        print('{0}:'.format(os.path.basename(path)))
        # https://stackoverflow.com/a/13335514
        #    [('foo',), ('bar',), ('baz',)]
        # -> ('foo', 'bar', 'baz')
        tables = zip(*tables)[0]
        cursors = {
                name: connection.execute('SELECT * FROM {0}'.format(name))
                for name in tables
        }

        sep = ' | '
        horiz_sep = '-' * 72
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
                        padding[k] = max(len(row[k]), len(k))
                        columns.append('{0:^{1}}'.format(k, padding[k]))
                    # print out the columns
                    print(*columns, sep=sep)
                    print(horiz_sep)
                # print out each row
                row_str = ['{0:<{1}}'.format(row[k]) for k in keys]
                print(*row_str, sep=sep)
                num += 1
            print('number of rows:', num)
        print(horiz_sep, end='\n\n')

def print_database(cfg, *databases):
    for db_name in databases:
        try:
            path = getattr(cfg, '{0}_db_path'.format(db_name))
        except AttributeError as e:
            logger.exception('Could not lookup \'{db_name}\':'
                    ' missing config option',
                    db_name=db_name,
                    exc_info=e,
            )
        else:
            if os.path.exists(path):
                do_print_database(path)

def handle(cfg, args):
    def convert(arg_str):
        return arg_str.replace('-', '_')

    ignore_keys = ['config']
    handlers = {
            convert(ADD_SUBREDDIT): add_subreddit,
            convert(RM_SUBREDDIT): rm_subreddit,
            convert(ADD_BLACKLIST): add_blacklist,
            convert(RM_BLACKLIST): rm_blacklist,
            convert(DUMP): print_database,
    }

    had_handleable_opt = False
    for opt in args:
        if opt not in ignore_keys and opt is not None:
            had_handleable_opt = True
            opt_key = convert(opt)
            opt_val = args[opt]
            try:
                handlers[opt_key](cfg, *opt_val)
            except KeyError as e:
                logger.exception('No option handler defined for \'{opt}\'!',
                        opt=opt,
                        exc_info=e,
                )

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

    databases = [
            # assumption: all database attributes end in '_DB_PATH'
            attr.split('_DB_PATH')[0].lower() for attr in dir(config)
            if attr.endswith('_DB_PATH')
    ]
    parser.add_argument('--{0}'.format(DUMP),
            metavar='NAME', nargs='+', choices=databases,
            help='Dump the specified databases to stdout',
    )

    args = vars(parser.parse_args())
    if __DEBUG__:
        logger.debug('args:\n{args}', args=pformat(args))
    return args


__all__ = [
        'handle',
        'parse',
]

