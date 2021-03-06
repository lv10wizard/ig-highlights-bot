## Instagram Highlight Reddit Bot

Replies to reddit posts/comments referencing instagram accounts with each
user's most popular media.

#### Dependencies

- praw >= 5.2

- requests

- bs4

- six

- pyenchant

- inflect

*For testing*:

- mock (for python2)

- pytest

python 2.7:

- `pip install -U praw requests bs4 six pyenchant inflect`

- for testing: `pip install -U mock pytest`

python 3.5+:

- `pip install -U praw requests bs4 six pyenchant inflect`

- for testing: `pip install -U pytest`

##### Running the bot

*Note: only tested in python 3.6 on cygwin 2.9 and python 3.5 on raspbian
gnu/linux 9, ubuntu 16.04*

1. Define [praw.ini](https://praw.readthedocs.io/en/latest/getting_started/configuration/prawini.html)

2. Modify config file

    - \*nix: `~/.config/igHighlightsBot/bot.cfg`

    - windows: `%APPDATA%/igHighlightsBot/bot.cfg`

    - mac: `~/Library/Preferences/igHighlightsBot/bot.cfg`

3. Enter your email in `<project root>/EMAIL` (this is used for the instagram
requests user-agent field)

4. `chmod +x main.py`

5. `./main.py`

    - `./main.py --help` for commandline options

##### Config:

*See [bot.cfg](bot.cfg) for the default config and some options documentation*

Note: time settings (eg. `instagram_cache_expire_time`) can either be defined
as a total number of seconds or as a string consisting of numbers followed by
units (ie, <number><unit><number><unit> ...).

The following units are recognized:

    s: seconds
    m: minutes
    h: hours
    d: days
    w: weeks
    M: months
    Y: years

So to specify 3 days, 2 hours, 2 minutes: `3d 2h 2m`

Floating point values are also recognized: `3.22Y`

##### praw.ini:

    [igHighlightsBot]
    client_id=PUBLIC_ID
    client_secret=CLIENT_SECRET
    username=BOT_ACCOUNT_NAME
    password=BOT_ACCOUNT_PASSWORD

- `username`/`password` are optional; the bot will prompt the user when it
requires login credentials (this may occur multiple times).

- The site-name section `[igHighlightsBot]` should match the `praw_sitename`
config setting.

##### File locations

*To delete all data saved by the program, run:* `./main.py --delete-data`
(will ask confirmation)

The program stores files in the following default locations:

- \*nix:

    - config: `$XDG_CONFIG_HOME/igHighlightsBot` (defaults to:
    `~/.config/igHighlightsBot`)

    - data: `$XDG_DATA_HOME/igHighlightsBot` (defaults to:
    `~/.local/share/igHighlightsBot`)

    - runtime: `$XDG_RUNTIME_DIR/igHighlightsBot` (defaults to:
    `/tmp/igHighlightsBot`)

- mac:

    - config: `$XDG_CONFIG_HOME/igHighlightsBot` (defaults to:
    `~/Library/Preferences/igHighlightsBot`)

    - data: `$XDG_DATA_HOME/igHighlightsBot` (defaults to:
    `~/Library/igHighlightsBot`)

    - runtime: `$XDG_RUNTIME_DIR/igHighlightsBot` (defaults to:
    `/tmp/igHighlightsBot`)

- win:

    - config: `%APPDATA%\igHighlightsBot`

    - data: `%APPDATA%\igHighlightsBot`

    - runtime: `%TMP%\igHighlightsBot`

