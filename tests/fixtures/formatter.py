import re

import pytest

from src.replies import Formatter


@pytest.fixture(scope='session')
def formatter_reply():
    """ Returns a mocked formatter reply """
    # TODO? actually call .format instead?
    username = '_foobar_'
    reply = [
            Formatter.HEADER_FMT.format(
                user_raw=username,
                user=re.sub(r'(_)', r'\\\1', username),
                link='https://www.instagram.com/foobar',
                suffix=Formatter.HEADER_HIGHLIGHTS,
            ),
            ' '.join(
                Formatter.HIGHLIGHT_FMT.format(
                    i=i, link='https://instagram.com/abcdefg',
                ) for i in range(15)
            ),
            Formatter.FOOTER_FMT,
    ]
    return Formatter.LINE_DELIM.join(reply)

