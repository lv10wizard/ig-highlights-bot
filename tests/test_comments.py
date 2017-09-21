import sys

if sys.version_info.major < 3:
    import mock
else:
    import unittest.mock as mock

import pytest

from src import comments


#

