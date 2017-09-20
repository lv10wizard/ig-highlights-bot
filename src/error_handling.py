import multiprocessing
import time

import praw

from src.util import logger


class ErrorHandler(object):
    """
    praw exception handling
    """

    # an event indicating that a process was rate-limited (meaning all
    # processes should wait until the originally rate-limited process is
    # finished sleeping)
    _rate_limited = multiprocessing.Event()

    def __str__(self):
        return self.__class__.__name__

    def handle(self, err, depth, callback,
            callback_args=(), callback_kwargs={}
    ):
        """
        Generic praw APIException handler. This method calls specific error
        handlers based on the given error's error_type.
        """
        if not isinstance(err, praw.exceptions.APIException):
            # only handle specific exception types
            raise

        elif depth > 10:
            # (N+1)-th time trying callback ... something's wrong
            raise

        try:
            handlers = self.__api_exception_handlers
        except AttributeError:
            handlers = {
                    'ratelimit': self.__handle_ratelimit,

                    # the following exist here as documentation of possible
                    # exceptions; not necessarily that they require a generic
                    # handler
                    # (this list may be incomplete)

                    # over character limit length
                    'too_long': self.__dummy_handler,

                    # doesn't exist (deleted, suspended, incorrect spelling)
                    'no_user': self.__dummy_handler,
                    'user_doesnt_exist': self.__dummy_handler,

                    # thing is archived
                    'too_old': self.__dummy_handler,

                    # text required (eg. comment reply)
                    'no_text': self.__dummy_handler,

                    # only text-posts allowed in subreddit
                    'no_links': self.__dummy_handler,
            }
            self.__api_exception_handlers = handlers

        try:
            handler_func = handlers[err.error_type.lower()]

        except (AttributeError, KeyError) as e:
            logger.id(logger.exception, self,
                    'Failed to handle {color_errclass} (\'{err_msg}\')!',
                    color_errclass='.'.join(
                        [err.__module__, err.__class__.__name__]
                    ),
                    err_msg=err.message,
                    exc_info=e,
            )

        else:
            logger.id(logger.debug, self,
                    'Handling {color_errtype}: \'{msg}\' ...',
                    color_errtype=err.error_type,
                    msg=err.message,
            )
            return handler_func(
                    err_type=err.error_type,
                    err=err,
                    callback=callback,
                    callback_args=callback_args,
                    callback_kwargs=callback_kwargs,
            )

    def __dummy_handler(self, err_type, err, *args, **kwargs):
        logger.id(logger.debug, self,
                '{color_errtype}: Ignoring ...',
                color_errtype=err_type,
        )

    def wait_for_rate_limit(self):
        if ErrorHandler._rate_limited.is_set():
            logger.id(logger.debug, self,
                    'Waiting on rate limit ...',
            )
        ErrorHandler._rate_limited.wait()

    def __handle_ratelimit(self, err_type, err, callback,
            callback_args, callback_kwargs
    ):
        # XXX: there is a chance that two processes end up here at the same
        # time - eg.
        #   procA: receives rate-limit error & starts handling but doesn't
        #           set the event yet
        #   procB: tries a rate-limited call, receives rate-limit error; also
        #           starts handling
        if ErrorHandler._rate_limited.is_set():
            logger.id(logger.debug, self,
                    '{color_errtype}: duplicate rate-limit detected!',
                    color_errtype=err_type,
            )
            # don't duplicate the rate-limit handling, just wait for the
            # original process to finish sleeping
            self.wait_for_rate_limit()

        else:
            ErrorHandler._rate_limited.set()

            delay = 10 * 60 # default delay
            logger.id(logger.debug, self,
                    '{color_errtype}: determining delay ...',
                    color_errtype=err_type,
            )
            try:
                delay = config.parse_time(err.message)

            except config.InvalidTime:
                logger.id(logger.debug, self,
                        'Could not determine delay from error message;'
                        ' using {time} (message: \'{msg}\')',
                        time=delay,
                        msg=err.message,
                )

            else:
                logger.id(logger.debug, self,
                        'Found delay: {time} (message: \'{msg}\')',
                        time=delay,
                        msg=err.message,
                )

            logger.id(logger.info, self,
                    'Rate limited! Retrying \'{callback}\' in {time} ...',
                    callback=callback.__name__,
                    time=delay,
            )
            time.sleep(delay)

            Error._rate_limited.clear()

        logger.id(logger.debug, self,
                'Issuing callback ...',
        )
        return callback(*callback_args, **callback_kwargs)


__all__ = [
        'ErrorHandler',
]

