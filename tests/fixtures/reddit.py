import sys

if sys.version_info.major < 3:
    import mock
else:
    import unittest.mock as mock


@mock.patch('praw.models.Comment', autospec=True)
def comment(comment):
    comment.id = 'dmzb5qa'
    comment.fullname = 't1_dmzb5qa'
    comment.subreddit_name_prefixed = 'u/lv10wizard'
    return comment

@mock.patch('praw.models.Submission', autospec=True)
def submission(submission):
    submission.id = '6zztml'
    submission.fullname = 't3_6zztml'
    submission.subreddit_name_prefixed = 'u/lv10wizard'
    return submission

@mock.patch('praw.models.Subreddit', autospec=True)
def subreddit(subreddit):
    subreddit.id = '3odt0'
    subreddit.fullname = 't5_3odt0'
    subreddit.display_name = 'u_lv10wizard'
    return subreddit

