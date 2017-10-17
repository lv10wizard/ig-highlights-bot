import os

import pytest

from src import database


def _test_path(tmpdir_factory, db):
    """
    Returns the path the database should use for testing
    """
    # assumption: basename( db.path ) is unique
    db_basename = os.path.basename(db.path)
    return tmpdir_factory.getbasetemp().join('data', db_basename)

@pytest.fixture(scope='module')
def bad_users_db(tmpdir_factory):
    """ BadUsernamesDatabase """
    db = database.BadUsernamesDatabase()
    db.path = str(_test_path(tmpdir_factory, db))
    return db

