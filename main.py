#!/usr/bin/env python2

import args
from src import config


if __name__ == '__main__':
    options = args.parse()

    import sys
    sys.exit(0)

    cfg = config.Config(options['config'])
    if args.handle(cfg, options):
        import sys
        sys.exit(0)

    from src.bot import IgHighlightsBot
    ig_highlights_bot = IgHighlightsBot(cfg)
    try:
        ig_highlights_bot.run_forever()

    finally:
        ig_highlights_bot.graceful_exit()

