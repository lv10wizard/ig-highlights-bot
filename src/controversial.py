from src import reddit
from src.config import parse_time
from src.mixins import (
        ProcessMixin,
        StreamMixin,
)
from src.util import logger


class Controversial(ProcessMixin, StreamMixin):
    """
    Bot-made comment deleter if any are below the score threshold
    """

    MIN_SCALE = 0.25
    MAX_DELAY = parse_time('1h')

    @staticmethod
    def choose_delay(score, threshold):
        """
        Chooses a delay relative to the MAX_DELAY based on the score and
        threshold. The further the score is from the threshold, the larger the
        delay. The closer the score is to the threshold, the smaller the delay.

        Returns the delay in seconds (float)
        """
        if score <= threshold:
            # the score is already below the threshold; just return the min
            # delay
            scale = Controversial.MIN_SCALE

        else:
            # scale the delay based on the score's distance from the threshold
            ratio = float(score) / float(threshold)
            # abs() in case the ratio is > 1 (eg. 100 / 5)
            scale = abs(1.0 - ratio)
            # don't scale below MIN_SCALE
            scale = max(Controversial.MIN_SCALE, scale)
            # don't scale above MAX_DELAY
            scale = min(scale, 1.0)

        return Controversial.MAX_DELAY * scale

    def __init__(self, cfg, rate_limited):
        ProcessMixin.__init__(self)
        StreamMixin.__init__(self, cfg, rate_limited)

    @property
    def _stream(self):
        # don't cache the controversial list generator since we want to check
        # all comments every pass
        return self._reddit.user.me().controversial(
                # the limit doesn't need to be > 100 (1 network request)
                # because if there are more than that many under-threshold
                # comments then
                #   1. the bot is probably unwanted in general and
                #   2. it will delete more the next pass
                time_filter='year', limit=100,
        )

    def _run_forever(self):
        while not self._killed.is_set():
            logger.id(logger.debug, self, 'Processing controversial ...')

            threshold = self.cfg.delete_comment_threshold
            # arbitrary large value guaranteed to be > threshold
            lowest_score = abs(threshold) * 1000
            for comment in self.stream:
                if self._killed.is_set():
                    break

                logger.id(logger.debug, self,
                        'Processing {color_comment} ({score}) ...',
                        color_comment=reddit.display_id(comment),
                        score=comment.score,
                )

                if comment.score <= threshold:
                    # score too low: delete the comment
                    logger.id(logger.info, self,
                            'Deleting {color_comment}: score too low'
                            ' ({score} < {threshold})',
                            color_comment=reddit.display_id(comment),
                            score=comment.score,
                            threshold=threshold,
                    )
                    try:
                        comment.delete()

                    except Exception:
                        # XXX: I'm not sure if delete can fail
                        logger.id(logger.warn, self,
                                'Failed to delete {color_comment}!',
                                color_comment=reddit.display_id(comment),
                                exc_info=True,
                        )

                else:
                    # note the lowest score we see above the threshold so the
                    # delay can be adjusted
                    lowest_score = min(lowest_score, comment.score)

            if not self._killed.is_set():
                # adjust the delay so that we are waiting less time between
                # checks if we've seen a comment score closer to the threshold
                # and more time if all comment scores are further from the
                # threshold.
                delay = Controversial.choose_delay(lowest_score, threshold)
                logger.id(logger.debug, self,
                        'Waiting {time} before checking controversial'
                        ' again ...',
                        time=delay,
                )
            self._killed.wait(delay)

        if self._killed.is_set():
            logger.id(logger.debug, self, 'Killed!')


__all__ = [
        'Controversial',
]
