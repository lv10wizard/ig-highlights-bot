import time

import requests

from src.util import logger


def choose_delay(delay):
    delay = max(1, delay)
    # exponentially increase delay
    delay *= 2
    # but don't let it run away
    delay = min(delay, 10 * 60)
    return delay

class Requestor(object):
    """
    requests wrapper with persistent sessions
    """

    def __init__(self, headers={}, cookies={}):
        self.__session = requests.Session()
        self.__update('headers', headers)
        self.__update('cookies', cookies)

    def __str__(self):
        result = [
                self.__class__.__name__,
                self.__session.headers['user-agent'],
        ]
        return ':'.join(result)

    def __update(self, attr, value):
        if isinstance(value, dict):
            if hasattr(self.__session, attr):
                attr_obj = getattr(self.__session, attr)
                if hasattr(attr_obj, 'update'):
                    logger.id(logger.debug, self,
                            'Updating {attr}: {value}',
                            attr=attr,
                            value=value,
                    )
                    attr_obj.update(value)

    def __choose_delay(self):
        try:
            delay = self.__last_delay

        except AttributeError:
            delay = 1

        # cache it so that we can continue to increase the delay
        delay = choose_delay(delay)
        self.__last_delay = delay
        return delay

    def request(self, url, method='get', allow_redirects=True, *args, **kwargs):
        response = None

        try:
            request_func = getattr(self.__session, method.lower())

        except AttributeError as e:
            logger.id(logger.exception, self,
                    'Cannot {method} \'{url}\': no such method!',
                    method=method.upper(),
                    url=url,
            )

        else:
            msg = ['{method} {url}']
            # TODO: don't log secrets (keys, passwords, etc)
            if args:
                msg.append('args: {func_args}')
            if kwargs:
                msg.append('kwargs: {func_kwargs}')
            logger.id(logger.debug, self,
                    '\n\t'.join(msg),
                    method=method.upper(),
                    url=url,
                    func_args=args,
                    func_kwargs=kwargs,
            )

            while response is None:
                try:
                    response = request_func(
                            url,
                            allow_redirects=allow_redirects,
                            *args, **kwargs
                    )

                except (
                        requests.ConnectionError,

                        # ECONNRESET
                        requests.exceptions.ChunkedEncodingError,
                ):
                    delay = self.__choose_delay()
                    logger.id(logger.debug, self,
                            '{method} {url}: waiting {time} ...',
                            method=method.upper(),
                            url=url,
                            time=delay,
                            exc_info=True,
                    )
                    # assumption: all ConnectionErrors indicate internet outage
                    time.sleep(delay)

                except (requests.Timeout, requests.TooManyRedirects) as e:
                    logger.id(logger.debug, self,
                            '{method} {url}',
                            method=method.upper(),
                            url=url,
                            exc_info=True,
                    )
                    # TODO? worth retrying ?
                    break

                else:
                    try:
                        # got a response, try to drop the cached delay
                        del self.__last_delay

                    except AttributeError:
                        pass

                    logger.id(logger.debug, self,
                            '{method} {url}: {status} {reason}',
                            method=method.upper(),
                            url=url,
                            status=response.status_code,
                            reason=response.reason,
                    )

        return response

