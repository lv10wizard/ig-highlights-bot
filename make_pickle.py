"""
Usage: <python2|python3> make_pickle.py COMMENT_ID PICKLE_NAME
    ** Run this in the project's root directory **

Pickles the given comment/submission and saves them to tests/fixtures/pickles
"""

import argparse
import os
import pickle
import sys

from praw.exceptions import PRAWException
from prawcore.exceptions import NotFound

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
            description='Pickles the comment/submission to'
            ' tests/fixtures/pickles'
    )
    parser.add_argument('thing_id', help='The thing id to pickle')
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

    # test if the id points to a comment
    # TODO: can/will/do comment ids and submission ids clash?
    thing = reddit_obj.comment(options['thing_id'])
    text = None

    try:
        # XXX: call .body to fetch the comment's data and to verify that it is
        # an actual comment.
        text = thing.body
    except PRAWException:
        # see if it's a submission
        thing = reddit_obj.submission(options['thing_id'])

        try:
            text = thing.title

        except (AttributeError, NotFound):
            logger.exception(
                    'Cannot pickle \'{color_id}\'.'
                    ' Is it a comment/submission?',
                    color_id=options['thing_id'],
            )
            raise

    if thing and text:
        logger.info('{color_thing} by {color_author}:\n{text}\n',
                color_thing=reddit.display_id(thing),
                color_author=reddit.author(thing),
                text=text,
        )
        logger.info('Pickling to \'{path}\' ...',
                path=path,
        )
        try:
            with open(path, 'wb') as fd:
                pickle.dump(thing, fd)

        except (IOError, OSError):
            logger.exception('Failed to pickle {color_thing}!',
                    color_thing=reddit.display_id(thing),
            )

        else:
            logger.info('Successfully pickled {color_thing} to \'{path}\'!',
                    color_thing=reddit.display_id(thing),
                    path=path,
            )

