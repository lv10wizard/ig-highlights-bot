import os
import time

from six import string_types

from ._database import (
        Database,
        UniqueConstraintFailed,
)
from src.util import logger


class InstagramDatabase(Database):
    """
    Cached instagram user data
    """

    PATH = 'instagram'

    BAD_FLAG = ':+$%!!!!!~BAD~!~USERNAME~!!!!!%$+:'
    PRIVATE_FLAG = ':+$%!!!!!~PRIVATE~!~ACCOUNT~!!!!!%$+:'

    def __init__(self, path, dry_run=False, *args, **kwargs):
        # XXX: take a dry_run argument in case one is passed, but don't use it
        # don't split instagram by run-mode
        Database.__init__(self, dry_run=False, *args, **kwargs)
        # override the path since this class defines per-user functionality
        self.path = path

    @property
    def _create_table_data(self):
        return (
                'cache('
                '   code TEXT PRIMARY KEY NOT NULL,'
                '   num_likes INTEGER NOT NULL,'
                '   num_comments INTEGER DEFAULT 0,'
                '   created REAL NOT NULL'
                ')',

                'followers('
                '   timestamp REAL NOT NULL,'
                '   num_followers INTEGER PRIMARY KEY NOT NULL'
                ')',
        )

    def __unpack(self, item):
        return (
                item['shortcode'],
                item['edge_media_preview_like']['count'],
                item['edge_media_to_comment']['count'],
                item['taken_at_timestamp'],

                # TODO: store the following as well
                # item['display_url'], # full-sized source url
                # item['edge_media_to_caption']['edges']['node']['text'],
        )

    def _insert(self, item):
        code, num_likes, num_comments, created = self.__unpack(item)
        self._db.execute(
                'INSERT INTO'
                ' cache(code, num_likes, num_comments, created)'
                ' VALUES(?, ?, ?, ?)',
                (code, num_likes, num_comments, created),
        )

    def _delete(self, codes):
        # TODO: .executemany instead
        def do_delete(code):
            self._db.execute(
                    'DELETE FROM cache WHERE code = ?',
                    (code,),
            )

        if hasattr(codes, '__iter__') and not isinstance(codes, string_types):
            for code in codes:
                do_delete(code)

        else:
            do_delete(codes)

    def _update(self, item):
        code, num_likes, num_comments, created = self.__unpack(item)
        self._db.execute(
                'UPDATE cache SET num_likes = ?, num_comments = ?'
                ' WHERE code = ?',
                (num_likes, num_comments, code),
        )

    def record_num_followers(self, num_followers):
        with self._db:
            try:
                self._db.execute(
                        'INSERT INTO followers(timestamp, num_followers)'
                        ' VALUES(?, ?)',
                        (time.time(), num_followers),
                )
            except UniqueConstraintFailed:
                pass

    def size(self):
        cursor = self._db.execute('SELECT count(*) FROM cache')
        return cursor.fetchone()[0]

    def get_all_codes(self):
        """
        Returns the set of all stored media codes
        """
        cursor = self._db.execute('SELECT code FROM cache')
        return set(row['code'] for row in cursor)

    def _get_max(self, col):
        """
        Returns the max value in the column
        """
        cursor = self._db.execute('SELECT MAX({0}) FROM cache'.format(col))
        return cursor.fetchone()[0]

    def _get_min(self, col):
        """
        Returns the min value in the column
        """
        cursor = self._db.execute('SELECT MIN({0}) FROM cache'.format(col))
        return cursor.fetchone()[0]

    def _get_avg(self, col):
        """
        Returns the avg value of the column
        """
        cursor = self._db.execute('SELECT AVG({0}) FROM cache'.format(col))
        return cursor.fetchone()[0]

    def _get_q1(self, col):
        """
        Returns the 25th percentile (1st quartile) of the given column
        """
        # https://stackoverflow.com/a/15766121
        cursor = self._db.execute(
                'SELECT AVG({0}) FROM (SELECT {0} FROM cache ORDER BY {0}'
                ' LIMIT 2 - (SELECT count(*) FROM cache) % 2'
                ' OFFSET (SELECT (count(*)/2 - 1) / 2 FROM cache))'.format(col)
        )
        return cursor.fetchone()[0]

    def _get_q2(self, col):
        """
        Returns the 50th percentile (2nd quartile) of the given column
        """
        # https://stackoverflow.com/a/15766121
        cursor = self._db.execute(
                'SELECT AVG({0}) FROM (SELECT {0} FROM cache ORDER BY {0}'
                ' LIMIT 2 - (SELECT count(*) FROM cache) % 2'
                ' OFFSET (SELECT count(*)/2 - 1 FROM cache))'.format(col)
        )
        return cursor.fetchone()[0]

    def _get_q3(self, col):
        """
        Returns the 75th percentile (3rd quartile) of the given column
        """
        # https://stackoverflow.com/a/15766121
        cursor = self._db.execute(
                'SELECT AVG({0}) FROM (SELECT {0} FROM cache ORDER BY {0}'
                ' LIMIT 2 - (SELECT count(*) FROM cache) % 2'
                ' OFFSET (SELECT (3*count(*)/2 - 1) / 2'
                ' FROM cache))'.format(col)
        )
        return cursor.fetchone()[0]

    @property
    def order_string(self):
        """
        Returns the SQLite query ORDER BY string

        (This exists so that args.py can utilize it)
        """
        # calculate the outer fences of the comment count so that we can gauge
        # comment outliers. media which generate a very large amount of comments
        # are either 1) controversial or some kind of high engagement piece of
        # media (eg. a giveaway) or 2) extremely popular.
        # https://www.wikihow.com/Calculate-Outliers
        q1_comments = self._get_q1('num_comments')
        q3_comments = self._get_q3('num_comments')
        iqr_comments = q3_comments - q1_comments
        outer_comments = (
                q1_comments - 3*iqr_comments,
                q3_comments + 3*iqr_comments
        )

        # normalize the column
        # https://stats.stackexchange.com/a/70807
        # XXX: multiply by 1.0 to force floating point calculations (in case the
        # weights are not floats)
        normalized_fmt = '{weight} * 1.0 * ({col} - {min}) / ({max} - {min})'
        normalized_likes = normalized_fmt.format(
                weight=1.0,
                col='num_likes',
                min=self._get_min('num_likes'),
                max=self._get_max('num_likes'),
        )

        avg_comments = self._get_avg('num_comments')
        max_comments = self._get_max('num_comments')
        normalized_comments = normalized_fmt.format(
                weight=1.0,
                col='num_comments',
                min=self._get_min('num_comments'),
                max=max_comments,
        )

        order = ('CASE'
                # exclude outlier comments
                ' WHEN (num_comments - {fence} >= {outlier_threshold}'
                # or media that has too high of a comment-to-like ratio
                # (these usually are not prototypical of the user's posts)
                ' OR 1.0 * (num_comments - {avg_comments}) / num_likes >= 0.08)'
                # but only if the like-count isn't very high; highly liked posts
                # are usually prototypical of the user's overall media.
                ' AND {normalized_likes} < 0.75'
                ' THEN 0'

                ' ELSE CASE'
                # order by likes if the comments avg is too high relative to
                # the max comment count. averages tend to skew low so if the
                # avg is high then that probably indicates the user has low
                # comment activity or that they don't have many posts.
                ' WHEN 1.0 * {avg_comments} / {max_comments} > 0.18'
                # or if the user's comment activity is too low
                ' OR {avg_comments} <= 10'
                '       THEN num_likes'
                # scale the likes count [0.1, 1] based on how far/close the
                # comments count is to its maximum value.
                # ie, low comment count relative to max -> 0.1 * likes
                #     high comment count                -> 1 * likes
                # XXX: 0.1 is the capped scale lower bound to account for
                # the minimum num_comments being 0
                '       ELSE MAX(0.1, {default_weight}) * num_likes'
                '       END'
                ' END DESC'.format(

                    fence=outer_comments[1],
                    # somewhat arbitrary threshold to exclude outliers
                    # (this just ensures that it is indeed an outlier)
                    outlier_threshold=outer_comments[1] - outer_comments[0],
                    # somewhat arbitrary base amount from which to judge the
                    # comments-to-likes ratio. this value makes the comparison
                    # apply more specifically to the user.
                    avg_comments=avg_comments,
                    # normalize so that we can meaningfully compare the value
                    normalized_likes=normalized_likes,

                    max_comments=max_comments,
                    default_weight=normalized_comments,
                )
        )

        return order

    def get_top_media(self, num=-1, start=0):
        """
        Returns a list containing at-most {num} most popular media links
                (may return a list with len < num if the database does not
                 contain enough links to populate the list)

        num (int, optional) - the number of media to return
                Default: -1 => return all media sorted .order_string
        start (int, optional) - the start index of media to return (this can
                    be used to exclude elements from the start of the set)
                Default: 0 => return media starting from the first element
        """
        from src.instagram import MEDIA_LINK_FMT

        cursor = self._db.execute(
                'SELECT code FROM cache ORDER BY {0}'.format(self.order_string)
        )
        media = []
        for i, row in enumerate(cursor):
            if len(media) == num:
                # stop once enough items have been collected
                break

            elif i < start:
                # skip elements before the start index
                continue

            link = MEDIA_LINK_FMT.format(row['code'])
            if link not in media:
                media.append(link)

        return media

    def _is_flagged(self, flag):
        """
        Returns whether the cache is flagged for the given *_FLAG flag
        """
        cursor = self._db.execute(
                'SELECT code FROM cache WHERE code = ?',
                (flag,),
        )
        return bool(cursor.fetchone())

    @property
    def is_flagged_as_bad(self):
        """
        Returns whether the cache is flagged as a bad user (no data or
                non-existant username)
        """
        return self._is_flagged(InstagramDatabase.BAD_FLAG)

    @property
    def is_private_account(self):
        """
        Returns whether the cache is flagged as a private account
        """
        return self._is_flagged(InstagramDatabase.PRIVATE_FLAG)

    def _flag(self, flag, is_update):
        """
        Flags the cache with the special *_FLAG
        """
        def flag_str(flag):
            if flag == InstagramDatabase.BAD_FLAG:
                return 'bad'
            elif flag == InstagramDatabase.PRIVATE_FLAG:
                return 'private'
            return '???'

        is_flagged = self._is_flagged(flag)
        if is_update or not is_flagged:
            with self._db:
                if not is_flagged:
                    logger.id(logger.debug, self,
                            'Flagging as {flag} ...',
                            flag=flag_str(flag),
                    )
                    # clear the cache so that the flag is the only element
                    cursor = self._db.execute('DELETE FROM cache')
                    if cursor.rowcount > 0:
                        # this probably means that the user made their account
                        # private
                        logger.id(logger.warn, self,
                                'Removed #{num} row{plural}!',
                                num=cursor.rowcount,
                                plural=('' if cursor.rowcount == 1 else 's'),
                        )
                    # XXX: co-opt the existing columns to flag the username
                    self._db.execute(
                            'INSERT INTO'
                            ' cache(code, num_likes, num_comments, created)'
                            ' VALUES(?, ?, ?, ?)',
                            (
                                flag,
                                -1,
                                -1,
                                time.time(),
                            ),
                    )

                else:
                    logger.id(logger.debug, self,
                            'Username is still {flag}: updating flag time ...',
                            flag=flag_str(flag),
                    )
                    self._db.execute(
                            'UPDATE cache SET created = ? WHERE code = ?',
                            (time.time(), flag),
                    )

        else:
            cursor = self._db.execute(
                    'SELECT created FROM cache WHERE code = ?',
                    (flag,),
            )
            row = cursor.fetchone()

            msg = ['Attempted to flag as {flag} again!']
            if row:
                msg.append('(flagged @ {strftime})')
                flag_time = row['created']
            else:
                flag_time = None
            logger.id(logger.warn, self,
                    ' '.join(msg),
                    flag=flag_str(flag),
                    strftime='%m/%d, %H:%M:%S',
                    strf_time=flag_time,
            )

    def flag_as_bad(self, is_update=True):
        """
        Flags the cache as bad (no data or non-existant user)
        """
        self._flag(InstagramDatabase.BAD_FLAG, is_update)

    def flag_as_private(self, is_update=True):
        """
        Flags the cache as a private user
        """
        self._flag(InstagramDatabase.PRIVATE_FLAG, is_update)


__all__ = [
        'InstagramDatabase',
]

