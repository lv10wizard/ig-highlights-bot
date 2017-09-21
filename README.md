## Instagram Highlight Reddit Bot

Responds to reddit comments linking to an instagram account with the ig
user's top liked media.

#### Dependencies

- praw >= 5.1 (> 4.0 may work; untested)

- requests

- bs4

*For testing*:

- mock (for python2)

- pytest

python 2.7:

- `pip install -U praw requests bs4`

- for testing: `pip install -U mock pytest`

python 3.5+:

- `pip install -U praw requests bs4`

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

*See [`src/config.py`](src/config.py) for some meager documentation of these options*

    [DEFAULT]
    max_replies_per_post = 15
    bad_actors_db_path = ~/igHighlightsBot/badactors.db
    replies_db_path = ~/igHighlightsBot/replies.db
    logging_path = ~/igHighlightsBot/logs
    instagram_db_path = ~/igHighlightsBot/instagram
    add_subreddit_threshold = 10
    instagram_queue_db_path = ~/igHighlightsBot/ig-queue.db
    instagram_cache_expire_time = 7d
    mentions_db_path = ~/igHighlightsBot/mentions.db
    num_highlights_per_ig_user = 15
    bad_actor_expire_time = 1d
    max_replies_per_comment = 2
    blacklist_temp_ban_time = 3d
    potential_subreddits_db_path = ~/igHighlightsBot/to-add-subreddits.db
    blacklist_db_path = ~/igHighlightsBot/blacklist.db
    subreddits_db_path = ~/igHighlightsBot/subreddits.db
    praw_sitename = igHighlightsBot
    app_name = igHighlightsBot
    instagram_rate_limit_db_path = ~/igHighlightsBot/ig-ratelimit.db
    send_debug_pm = true
    bad_actor_threshold = 3
    messages_db_path = ~/igHighlightsBot/messages.db
    max_replies_in_comment_thread = 3

##### praw.ini:

    [igHighlightsBot]
    client_id=PUBLIC_ID
    client_secret=CLIENT_SECRET
    username=BOT_ACCOUNT_NAME
    password=BOT_ACCOUNT_PASSWORD

username/password are optional; the bot will prompt the user when it
requires login credentials (this may occur multiple times).

