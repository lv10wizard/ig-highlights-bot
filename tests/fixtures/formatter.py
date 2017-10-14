import pytest

from src.replies import Formatter


@pytest.fixture(scope='session')
def formatter_reply():
    """ Returns a mocked formatter reply """
    # TODO? actually call .format instead?
    reply = [
            Formatter.HEADER_FMT.format(
                user='foobar', link='https://www.instagram.com/foobar',
            ),
            ' '.join(
                Formatter.HIGHLIGHT_FMT.format(
                    i=i, link='https://instagram.com/abcdefg',
                ) for i in range(15)
            ),
            Formatter.FOOTER_FMT,
    ]
    return Formatter.LINE_DELIM.join(reply)

