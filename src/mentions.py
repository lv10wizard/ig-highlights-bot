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

    def __init__(self, cfg, submission_queue):
        ProcessMixin.__init__(self)
        StreamMixin.__init__(self, cfg)

        self.submission_queue = submission_queue

    @property
    def _stream_method(self):
        self._reddit.inbox.mentions

    def _run_forever(self):
        mentions_db = database.MentionsDatabase(self.cfg.mentions_db_path)
        delay = 5 * 60

        try:
            while not self._killed.is_set():
                logger.id(logger.debug, self, 'Processing mentions ...')
                for mention in self.stream:
                    if mentions_db.has_seen(mention):
                        # assumption: inbox.mentions fetches newest -> oldest
                        logger.id(logger.debug, self,
                                'I\'ve already processed {color_post} from'
                                ' {color_from}!',
                                color_post=reddit.display_fullname(mention),
                                color_from=(
                                    mention.author.name
                                    if bool(mention.author)
                                    else '[deleted/removed]'
                                ),
                        )
                        break

                    elif self._killed.is_set():
                        logger.id(logger.debug, self, 'Killed!')

                    elif mention is None:
                        break

                    with mentions_db:
                        mentions_db.insert(mention)

                    data = (mention.submission, mention)
                    self.submission_queue.put(data)

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

