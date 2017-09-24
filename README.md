## Instagram Highlight Reddit Bot

Responds to reddit comments linking to an instagram account with the ig
user's top liked media.

#### Dependencies

- praw >= 5.1 (> 4.0 may work; untested)

- requests

- bs4

- six

*For testing*:

- mock (for python2)

- pytest

python 2.7:

- `pip install -U praw requests bs4 six`

- for testing: `pip install -U mock pytest`

python 3.5+:

- `pip install -U praw requests bs4 six`

- for testing: `pip install -U pytest`

##### Running the bot

1. Define praw.ini (see: https://praw.readthedocs.io/en/latest/getting_started/configuration/prawini.html)

2. Modify config file

    - \*nix: `~/.config/igHighlightsBot/bot.cfg`

    - windows: `%APPDATA%/igHighlightsBot/bot.cfg`

    - mac: `~/Library/Application Support/igHighlightsBot/bot.cfg`

3. Enter your email in '<project root>/EMAIL'

4. `chmod +x main.py`

5. `./main.py`

##### default config:

*See [ bot.cfg ](bot.cfg) for the default config*

##### praw.ini:

    [igHighlightsBot]
    client_id=PUBLIC_ID
    client_secret=CLIENT_SECRET
    username=BOT_ACCOUNT_NAME
    password=BOT_ACCOUNT_PASSWORD

username/password are optional; the bot will prompt the user when it
requires login credentials (this may occur multiple times).

