#!/usr/bin/env python3

import sys

from six import (
        integer_types,
        string_types,
)

import args
import constants
from constants import __DEBUG__
from src import config
from src.util import logger


def init_logger(cfg=None, options=None):
    """
    Initializes logging with the specified options
    """
    if cfg and options:
        # set the appropriate formatter
        if options['logging_no_color'] or not cfg.colorful_logs:
            formatter = logger.NoColorFormatter()
        else:
            formatter = logger.Formatter()

        # set the appropriate level
        level = options['logging_level'] or cfg.logging_level

        # set the appropriate logging root dir
        handlers = []
        path = options['logging_path'] or cfg.logging_path
        if path:
            hndlr = logger.ProcessFileHandler(path)
            hndlr.setLevel(level)
            handlers.append(hndlr)
        else:
            if isinstance(level, string_types):
                if level.isdigit():
                    level = int(level)

                else:
                    # check that the passed-in level is valid
                    try:
                        getattr(logger, level)
                    except AttributeError:
                        level = cfg.logging_level
                    finally:
                        # convert into the level code
                        level = getattr(logger, level)

            elif not isinstance(level, integer_types):
                level = cfg.logging_level
                if level.isdigit():
                    level = int(level)
                elif isinstance(level, string_types):
                    level = getattr(logger, level)
                else:
                    raise TypeError('Unhandled logging-level: \'{0}\''.format(
                        level
                    ))

            # no path defined: log to stdout/stderr
            if level <= logger.WARNING:
                stdout_filter = logger.LevelFilter(level, logger.WARNING)
                stdout_handler = logger.ProcessStreamHandler(stream=sys.stdout)
                stdout_handler.addFilter(stdout_filter)
                handlers.append(stdout_handler)
            if level <= logger.CRITICAL:
                min_level = max(logger.ERROR, level)
                stderr_filter = logger.LevelFilter(min_level, logger.CRITICAL)
                stderr_handler = logger.ProcessStreamHandler(stream=sys.stderr)
                stderr_handler.addFilter(stderr_filter)
                handlers.append(stderr_handler)

        logger.clear_handlers()
        for hndlr in handlers:
            hndlr.setFormatter(formatter)
            logger.add_handler(hndlr)

    else:
        # set up any initial logging to stdout
        handler = logger.ProcessStreamHandler(stream=sys.stdout)
        level = logger.DEBUG if __DEBUG__ else logger.INFO
        handler.setLevel(level)
        handler.setFormatter(
                logger.Formatter(fmt=logger.Formatter.FORMAT_NO_DATE)
        )
        logger.clear_handlers()
        logger.add_handler(handler)

if __name__ == '__main__':
    init_logger()
    options = args.parse()

    # assign the dry_run arg as a "global" of sorts so that it doesn't have to
    # be passed to everything
    constants.dry_run = options['dry_run']
    cfg = config.Config(options['config'])
    if args.handle(cfg, options):
        sys.exit(0)

    init_logger(cfg, options)

    from src.bot import IgHighlightsBot
    ig_highlights_bot = IgHighlightsBot(cfg)
    try:
        ig_highlights_bot.run_forever()

    except Exception:
        logger.critical('An uncaught exception occured!',
                exc_info=True,
        )

    finally:
        ig_highlights_bot.graceful_exit()
        logger.info('Exiting ...')
        logger.shutdown()

