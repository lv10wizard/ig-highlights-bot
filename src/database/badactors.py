from _database import Database


class BadActorsDatabase(Database):
    """
    Database of reddit users that have exhibited bad behaior potentially
    worthy of a temp ban (eg. linking to many 404s in a "short" timeframe)
    """

    def __init__(self, path, cfg):
        Database.__init__(self, path)
        self.cfg = cfg

    def _create_table_data(self):
        columns = [
                'created_utc REAL PRIMARY KEY NOT NULL',
                'author_name TEXT NOT NULL COLLATE NOCASE',
                'data TEXT',
        ]

        return (
                # active set of bad actors
                'active({0})'.format(','.join(columns)),

                # inactive set of bad actors (pruned due to time)
                # these are kept in case I might want to refine how temp
                # blacklisting works (eg. temp blacklist if total > threshold)
                'inactive({0})'.format(','.join(columns)),
        )

    def _insert(self, thing, data):
        self.__prune(thing)
        if thing.author:
            self._db.execute(
                    'INSERT INTO active(created_utc, author_name, data)'
                    ' VALUES(?, ?, ?)',
                    (thing.created_utc, thing.author.name, data),
            )

    def __prune(self, thing):
        """
        Attempts to prune expired active records.
        A record is expired if the elapsed time between the stored created_utc
        and the given thing's created_utc exceeds the config-defined expiration
        time:
            thing.created - stored_created > expire
            thing.created - expire         > stored_created

        created_utc is used to gauge the timeframe the user was behaving in a
        poor manner. If, instead, local time (time.time()) was used then the
        timeframe judged would be whenever the bot happened to fetch the given
        thing (which wouldn't be particularly useful).
        """

        if thing.author:
            # assumption: this thing's created_utc is > stored timestamps
            # (ie, it is newer)
            expire_utc = thing.created_utc - self.cfg.bad_actor_expire_time
            cursor = self._db.execute(
                    'SELECT * FROM active'
                    ' WHERE author_name = ? AND created_utc < ?',
                    (thing.author.name, expire_utc),
            )

            pruned = []
            for row in cursor:
                self._db.execute(
                        'DELETE FROM active WHERE'
                        ' created_utc = ?'
                        ' author_name = ?'
                        ' data = ?',
                        row,
                )
                self._db.execute(
                        'INSERT INTO inactive(created_utc, author_name, data)'
                        ' VALUES(?, ?, ?)',
                        row,
                )
                pruned.append(row)

            if pruned:
                debug_rows = [
                        '{0}, {1}, {2}'.format(
                            row['created_utc'],
                            row['author_name'],
                            row['data'],
                        ) for row in pruned
                ]
                logger.prepend_id(logger.debug, self,
                        'Pruned #{num} (created: {created} by {author}):'
                        '\n{rows}',
                        num=len(pruned),
                        created=thing.created_utc,
                        author=thing.author.name,
                        rows='\n'.join(debug_rows),
                )
                self._db.commit()

    def count(self, thing):
        """
        Returns the number of active entries for thing's author
                -1 if thing has no author (deleted/removed)
        """
        self.__prune(thing)
        if thing.author:
            cursor = self._db.execute(
                    'SELECT created_utc FROM active WHERE author_name = ?',
                    (thing.author.name,),
            )
            return len(cursor.fetchall())
        return -1


__all__ = [
        'BadActorsDatabase',
]

