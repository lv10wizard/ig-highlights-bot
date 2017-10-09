"""
Usage: <python2|python3> make_pickle.py COMMENT_ID PICKLE_NAME
    ** Run this in the project's root directory **

Pickles the given comment and saves them to tests/fixtures/pickles
"""

import argparse
import os
import pickle
import sys

from praw.exceptions import PRAWException

from src import reddit
from src.config import Config
from src.util import logger


if __name__ == '__main__':
    handler = logger.ProcessStreamHandler(stream=sys.stdout)
    handler.setLevel(logger.DEBUG)
    handler.setFormatter(logger.Formatter(fmt=logger.Formatter.FORMAT_NO_DATE))
    logger.clear_handlers()
    logger.add_handler(handler)

    parser = argparse.ArgumentParser(
            description='Pickles the comment to tests/fixtures/pickles'
    )
    parser.add_argument('comment_id', help='The comment id to pickle')
    parser.add_argument('pickle_name',
            help='The filename to save the pickle as',
    )
    options = vars(parser.parse_args())

    logger.debug(options)

    cfg = Config()
    # XXX: pass a dummy rate_limited object just to initialize; the reddit obj
    # shouldn't actually use it here.
    reddit_obj = reddit.Reddit(cfg, None)

    basedir = os.path.join('tests', 'fixtures', 'pickles')
    filename = '{0}.py{1}.pickle'.format(
            options['pickle_name'], sys.version_info.major
    )
    path = os.path.join(basedir, filename)
    if os.path.exists(path):
        logger.info('\'{path}\' exists. Exiting ...')
        sys.exit(0)

    comment = reddit_obj = reddit_obj.comment(options['comment_id'])
    try:
        # XXX: call .body to fetch the comment's data and to verify that it is
        # an actual comment.
        body = comment.body
    except PRAWException:
        logger.exception('Cannot pickle \'{color_cid}\'. Is it a comment?',
                color_cid=options['comment_id'],
        )
        raise

    else:
        logger.info('{color_comment} by {color_author}:\n{body}\n',
                color_comment=reddit.display_id(comment),
                color_author=reddit.author(comment),
                body=body,
        )
        logger.info('Pickling to \'{path}\' ...',
                path=path,
        )
        try:
            with open(path, 'wb') as fd:
                pickle.dump(comment, fd)

        except (IOError, OSError):
            logger.exception('Failed to pickle {color_comment}!',
                    color_comment=reddit.display_id(comment),
            )

        else:
            logger.info('Successfully pickled {color_comment} to \'{path}\'!',
                    color_comment=reddit.display_id(comment),
                    path=path,
            )

