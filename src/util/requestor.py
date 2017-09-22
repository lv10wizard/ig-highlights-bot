import time

import requests

from src.util import logger


def choose_delay(delay):
    delay = max(1, delay)
    # exponentially increase delay
    delay *= 2
    # but don't let it run away
    delay = max(delay, 10 * 60)
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

    def request(url, method='get', *args, **kwargs):
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
            if args:
                msg.append('args: {args}')
            if kwargs:
                msg.append('kwargs: {kwargs}')
            logger.id(logger.debug, self,
                    '\n\t'.join(msg),
                    method=method.upper(),
                    url=url,
                    args=args,
                    kwargs=kwargs,
            )

            while not response:
                try:
                    response = request_func(url, *args, **kwargs)

                except requests.ConnectionError as e:
                    delay = self.__choose_delay()
                    logger.id(logger.exception, self,
                            '{method} {url}: waiting {time} ...',
                            method=method.upper(),
                            url=url,
                            time=delay,
                    )
                    # assumption: all ConnectionErrors indicate internet outage
                    time.sleep(delay)

                except (requests.Timeout, requests.TooManyRedirects) as e:
                    logger.id(logger.exception, self,
                            '{method} {url}',
                            method=method.upper(),
                            url=url,
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

