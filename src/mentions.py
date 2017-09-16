from praw.models import util as praw_util
from utillib import logger

from src import (
        base,
        config,
        database,
        reddit,
)


class Mentions(base.ProcessBase):
    """
    Username mentions (in comments) parser
    """

    def __init__(self, cfg, submission_queue):
        base.ProcessBase.__init__(self)

        self.cfg = cfg
        self.submission_queue = submission_queue

    def _run_forever(self):
        reddit_obj = reddit.Reddit(self.cfg)
        mentions_db = database.MentionsDatabase(self.cfg.mentions_db_path)
        mentions_stream = praw_util.stream_generator(
                reddit_obj.inbox.mentions,
                pause_after=0,
        )
        delay = 5 * 60

        try:
            while not self._killed.is_set():
                logger.prepend_id(logger.debug, self, 'Processing mentions ...')
                for mention in mentions_stream:
                    if mentions_db.has_seen(mention):
                        # assumption: inbox.mentions fetches newest -> oldest
                        logger.prepend_id(logger.debug, self,
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
                        logger.prepend_id(logger.debug, self, 'Killed!')

                    elif mention is None:
                        break

                    with mentions_db:
                        mentions_db.insert(mention)

                    data = (mention.submission, mention)
                    self.submission_queue.put(data)

                if not self._killed.is_set():
                    logger.prepend_id(logger.debug, self,
                            'Waiting {time} before checking messages again ...',
                            time=delay,
                    )
                self._killed.wait(delay)

        except Exception as e:
            # TODO? only catch praw errors
            logger.prepend_id(logger.error, self,
                    'Something went wrong! Message processing terminated.', e,
            )


__all__ = [
        'Mentions',
]

