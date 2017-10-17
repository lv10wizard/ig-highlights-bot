from contextlib import contextmanager
import re

from src.replies import Formatter


@contextmanager
def _seed(db, thing):
    ig_usernames = Formatter.ig_users_in(thing.body)
    for ig_user in ig_usernames:
        db.insert(ig_user, thing)
    yield db
    db.rollback()

def test_bad_users_init(bad_users_db):
    assert bad_users_db
    assert bad_users_db.path.endswith(bad_users_db.PATH)

def test_bad_users_insert(bad_users_db, _cassiebrown_bot_reply):
    with _seed(bad_users_db, _cassiebrown_bot_reply):
        row = bad_users_db._db.execute('SELECT * FROM bad_usernames').fetchone()
        assert row['string'] == '_cassiebrown_'
        assert row['thing_fullname'] == _cassiebrown_bot_reply.fullname
        assert row['score'] == _cassiebrown_bot_reply.score

def test_bad_users_contains(bad_users_db, _cassiebrown_bot_reply):
    with _seed(bad_users_db, _cassiebrown_bot_reply):
        assert '_cassiebrown_' in bad_users_db

def test_bad_users_delete(bad_users_db, _cassiebrown_bot_reply):
    with _seed(bad_users_db, _cassiebrown_bot_reply):
        ig_usernames = Formatter.ig_users_in(_cassiebrown_bot_reply.body)
        bad_users_db.delete(ig_usernames[0])
        cursor = bad_users_db._db.execute('SELECT count(*) FROM bad_usernames')
        assert cursor.fetchone()[0] == 0

def test_bad_users_get_username_strings_raw(
        bad_users_db, _cassiebrown_bot_reply
):
    with _seed(bad_users_db, _cassiebrown_bot_reply):
        strings = bad_users_db.get_bad_username_strings_raw()
        assert len(strings) == 1
        assert '_cassiebrown_' in strings

def test_bad_users_get_username_patterns(bad_users_db, _cassiebrown_bot_reply):
    with _seed(bad_users_db, _cassiebrown_bot_reply):
        patterns = bad_users_db.get_bad_username_patterns()
        assert len(patterns) == 1
        assert re.search('^{0}$'.format('|'.join(patterns)), '_cassiebrown_')

