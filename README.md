## Instagram Highlight Reddit Bot

Responds to reddit comments linking to an instagram account with the ig
user's top liked media.

#### Dependencies

python2.7

- praw >= 5.1 (> 4.0 may work; untested)

- utillib

*For testing*:

- mock

- pytest

##### praw.ini:

    [ig-highlights-bot]
    client_id=PUBLIC_ID
    client_secret=CLIENT_SECRET
    username=BOT_ACCOUNT_NAME
    password=BOT_ACCOUNT_PASSWORD

