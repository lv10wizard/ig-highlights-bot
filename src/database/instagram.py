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
                '   num_likes INTEGER NOT NULL'
                ')'
        )

    def __unpack(self, item):
        return item['code'], item['link'], item['likes']['count']

    def _insert(self, item):
        code, link, num_likes = self.__unpack(item)
        self._db.execute(
                'INSERT INTO cache(code, link, num_likes) VALUES(?, ?, ?)',
                (code, link, num_likes),
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
        code, link, num_likes = self.__unpack(item)
        self._db.execute(
                'UPDATE cache SET num_likes = ? WHERE code = ? AND link = ?',
                (num_likes, code, link),
        )

    def get_all_codes(self):
        """
        Returns the set of all stored media codes
        """
        cursor = self._db.execute('SELECT code FROM cache')
        return set(row['code'] for row in cursor)

    def get_top_media(self, num):
        """
        Returns a list containing at-most {num} top-liked media links
                (may return a list with len < num if the database does not
                 contain enough links to populate the list)
        """
        cursor = self._db.execute(
                'SELECT link FROM cache ORDER BY num_likes DESC'
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

