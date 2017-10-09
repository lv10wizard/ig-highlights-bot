import os

from six import string_types

from ._database import Database


class InstagramDatabase(Database):
    """
    Cached instagram user data
    """

    PATH = Database.PATH_FMT.format('instagram')

    @property
    def _create_table_data(self):
        return (
                'cache('
                '   code TEXT PRIMARY KEY NOT NULL,'
                '   link TEXT NOT NULL,'
                '   num_likes INTEGER NOT NULL,'
                '   num_comments INTEGER DEFAULT 0,'
                '   created REAL NOT NULL'
                ')'
        )

    def __unpack(self, item):
        return (
                item['code'],
                item['link'],
                item['likes']['count'],
                item['comments']['count'],
                item['created_time'],
        )

    def _insert(self, item):
        code, link, num_likes, num_comments, created = self.__unpack(item)
        self._db.execute(
                'INSERT INTO'
                ' cache(code, link, num_likes, num_comments, created)'
                ' VALUES(?, ?, ?, ?, ?)',
                (code, link, num_likes, num_comments, created),
        )

    def _delete(self, codes):
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
        code, link, num_likes, num_comments, created = self.__unpack(item)
        self._db.execute(
                'UPDATE cache SET num_likes = ?, num_comments = ?'
                ' WHERE code = ? AND link = ?',
                (num_likes, num_comments, code, link),
        )

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

    @property
    def order_string(self):
        """
        Returns the SQLite query ORDER BY string

        (This exists so that args.py can utilize it)
        """
        min_likes = self._get_min('num_likes')
        max_likes = self._get_max('num_likes')
        weight_likes = 0.25
        min_comments = self._get_min('num_comments')
        max_comments = self._get_max('num_comments')
        # comments seem to be a better indicator of activity/popularity
        weight_comments = 1.0

        # sort the data by a combination of likes/comments count so that we
        # get a set that is ordered by most active first
        # https://stats.stackexchange.com/a/70807
        # XXX: multiply by 1.0 to force floating point calculations (in case the
        # weights are not floats)
        normalized_fmt = '{weight} * 1.0 * ({col} - {min}) / ({max} - {min})'
        normalized_likes = normalized_fmt.format(
                weight=weight_likes,
                col='num_likes',
                min=min_likes,
                max=max_likes,
        )
        normalized_comments = normalized_fmt.format(
                weight=weight_comments,
                col='num_comments',
                min=min_comments,
                max=max_comments,
        )
        order = '{0} + {1}'.format(normalized_likes, normalized_comments)
        order += ' DESC'
        return order

    def get_top_media(self, num):
        """
        Returns a list containing at-most {num} most popular media links
                (may return a list with len < num if the database does not
                 contain enough links to populate the list)
        """
        cursor = self._db.execute(
                'SELECT link FROM cache ORDER BY {0}'.format(self.order_string)
        )
        media = []
        for row in cursor:
            if len(media) == num:
                break
            if row['link'] not in media:
                media.append(row['link'])

        return media


__all__ = [
        'InstagramDatabase',
]

