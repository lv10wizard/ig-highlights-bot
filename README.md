## Instagram Highlight Reddit Bot

Responds to reddit comments linking to an instagram account with the ig
user's top liked media.

#### Dependencies

python2.7

- praw >= 5.1 (> 4.0 may work; untested)

*For testing*:

- mock

- pytest

##### Running the bot

1. Define praw.ini (see: https://praw.readthedocs.io/en/latest/getting_started/configuration/prawini.html)

2. Enter your email in '<project root>/EMAIL'

3. `chmod +x main.py`

4. `./main.py`

##### praw.ini:

    [ig-highlights-bot]
    client_id=PUBLIC_ID
    client_secret=CLIENT_SECRET
    username=BOT_ACCOUNT_NAME
    password=BOT_ACCOUNT_PASSWORD

