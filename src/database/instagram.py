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
        normalized_comments = normalized_fmt.format(
                weight=1.0,
                col='num_comments',
                min=self._get_min('num_comments'),
                max=self._get_max('num_comments'),
        )

        order = ('CASE'
                # exclude outlier comments
                ' WHEN num_comments - {0} >= {1} AND {2} < 0.4 THEN 0'
                ' ELSE {3} END DESC'.format(
                    outer_comments[1],
                    # somewhat arbitrary threshold to exclude outliers
                    outer_comments[1] - outer_comments[0],
                    # only exclude if likes are low. highly liked posts are
                    # usually prototypical of the user's overall media.
                    normalized_likes,

                    # scale the likes count [0,1] based on how far/close the
                    # comments count is to its maximum value.
                    # ie, low comment count relative to max -> 0 * likes
                    #     high comment count                -> 1 * likes
                    normalized_comments + ' * num_likes',
                )
        )

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

