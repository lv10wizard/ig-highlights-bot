from src import (
        reddit,
        replies,
)
from src.mixins import (
        ProcessMixin,
        SubredditsSubmissionsStreamMixin,
)
from src.util import logger


class Submissions(ProcessMixin, SubredditsSubmissionsStreamMixin):
    """
    Submissions process
    """

    def __init__(self, cfg, rate_limited, blacklist):
        ProcessMixin.__init__(self)
        SubredditsSubmissionsStreamMixin.__init__(self, cfg, rate_limited)
        self.blacklist = blacklist

    def _run_forever(self):
        """
        Bot submission stream parsing
        """
        self.filter = replies.Filter(
                self.cfg, self._reddit.username_raw, self.blacklist
        )

        delay = 60

        while not self._killed.is_set():
            for submission in self.stream:
                if not submission or self._killed.is_set():
                    break

                logger.id(logger.info, self,
                        'Processing {color_submission}',
                        color_submission=reddit.display_id(submission),
                )

                ig_usernames = self.filter.replyable_usernames(submission)
                if ig_usernames:
                    self.filter.enqueue(submission, ig_usernames)

            self._killed.wait(delay)

        if self._killed.is_set():
            logger.id(logger.debug, self, 'Killed!')


__all__ = [
        'Submissions',
]

