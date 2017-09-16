from _database import Database


class InstagramDatabase(Database):
    """
    Cached instagram user data
    """

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

    def _delete(self, items):
        def do_delete(item):
            code, link, num_likes = self.__unpack(item)
            self._db.execute(
                    'DELETE FROM cache'
                    ' WHERE code = ?'
                    ' AND link = ?'
                    ' AND num_likes = ?',
                    (code, link, num_likes),
            )

        if hasattr(items, '__iter__'):
            for item in items:
                do_delete(item)

        else:
            do_delete(items)

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
        curor = self._db.execute('SELECT link FROM cache ORDER BY likes DESC')
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

