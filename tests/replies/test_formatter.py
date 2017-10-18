from src.replies import Formatter

def test_formatter_finds_users_in_reply(formatter_reply):
    users = Formatter.ig_users_in(formatter_reply)
    assert len(users) == 1
    assert users[0] == '_foobar_'

def test_formatter_does_not_over_match_users_in_reply():
    assert not Formatter.ig_users_in('foobar')
    assert not Formatter.ig_users_in('[](#bot)')
    assert not Formatter.ig_users_in('This is a test comment')

