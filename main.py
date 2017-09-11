#!/usr/bin/env python2

import argparse

from utillib import logger

from src import (
        bot,
        config,
)


def parse_args():
    parser = argparse.ArgumentParser(
            description=''
    )
    return vars(parser.parse_args())

if __name__ == '__main__':
    cfg = config.Config()
    ig_highlights_bot = bot.IgHighlightsBot(cfg)
    try:
        ig_highlights_bot.run_forever()

    finally:
        ig_highlights_bot.graceful_exit()

