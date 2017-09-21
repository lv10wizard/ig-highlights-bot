## Instagram Highlight Reddit Bot

Responds to reddit comments linking to an instagram account with the ig
user's top liked media.

#### Dependencies

python 2.7+ or 3.5+

- praw >= 5.1 (> 4.0 may work; untested)

- requests

- bs4

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

username/password are optional; the bot will prompt the user when it
requires login credentials (this may occur multiple times).

