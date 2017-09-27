from src import (
        config,
        database,
        reddit,
)
from src.mixins import (
        ProcessMixin,
        StreamMixin,
)
from src.util import logger


class Mentions(ProcessMixin, StreamMixin):
    """
    Username mentions (in comments) parser
    """

    def __init__(self, cfg, rate_limited, rate_limit_time, submission_queue):
        ProcessMixin.__init__(self)
        StreamMixin.__init__(self, cfg, rate_limited, rate_limit_time)

        self.submission_queue = submission_queue

    @property
    def _stream_method(self):
        self._reddit.inbox.mentions

    def _run_forever(self):
        mentions_db = database.MentionsDatabase()
        delay = 15 # too long?

        try:
            while not self._killed.is_set():
                logger.id(logger.debug, self, 'Processing mentions ...')
                for mention in self.stream:
                    if mentions_db.has_seen(mention):
                        # assumption: inbox.mentions fetches newest -> oldest
                        logger.id(logger.debug, self,
                                'I\'ve already processed {color_mention} from'
                                ' {color_from}!',
                                color_mention=reddit.display_fullname(mention),
                                color_from=reddit.author(mention),
                        )
                        break

                    elif self._killed.is_set():
                        logger.id(logger.debug, self, 'Killed!')

                    elif mention is None:
                        break

                    try:
                        with mentions_db:
                            mentions_db.insert(mention)
                    except database.UniqueConstraintFailed:
                        # this means there is a bug in has_seen
                        logger.id(logger.exception, self,
                                'Attempted to process duplicate submission:'
                                ' {color_mention} from {color_from}!',
                                color_mention=reddit.display_fullname(mention),
                                color_from=reddit.author(mention),
                        )
                        break

                    data = (mention, mention.submission)
                    try:
                        with self.submission_queue:
                            self.submission_queue.insert(*data)
                    except database.UniqueConstraintFailed:
                        # this shouldn't happen
                        logger.id(logger.exception, self,
                                'Failed to queue submission \'{color_post}\''
                                ' from {color_from}!',
                                color_post=reddit.display_fullname(
                                    mention.submission
                                ),
                                color_from=reddit.author(mention),
                        )
                        # TODO? raise

                if not self._killed.is_set():
                    logger.id(logger.debug, self,
                            'Waiting {time} before checking messages again ...',
                            time=delay,
                    )
                self._killed.wait(delay)

        except Exception as e:
            # TODO? only catch praw errors
            logger.id(logger.exception, self,
                    'Something went wrong! Message processing terminated.',
            )


__all__ = [
        'Mentions',
]

