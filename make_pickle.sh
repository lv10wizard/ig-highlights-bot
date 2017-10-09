#!/usr/bin/env bash

COMMENT_ID="$1"
FILENAME="$2"

if [[ ! -z "$COMMENT_ID" && ! -z "$FILENAME" ]]; then
    python2 make_pickle.py "$COMMENT_ID" "$FILENAME" \
        && python3 make_pickle.py "$COMMENT_ID" "$FILENAME"
else
    echo "Need comment_id and filename!"
fi

