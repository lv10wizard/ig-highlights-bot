from ._database import (
        Database,
        UniqueConstraintFailed,
)


class BadActorsDatabase(Database):
    """
    Database of reddit users that have exhibited bad behaior potentially
    worthy of a temp ban (eg. linking to many 404s in a "short" timeframe)
    """

    PATH = 'bad-actors.db'

    def __init__(self, cfg, *args, **kwargs):
        Database.__init__(self, *args, **kwargs)
        self.cfg = cfg

    def __contains__(self, thing):
        """
        Returns whether the thing has ever been flagged as a bad actor
        """
        from src import reddit

        fullname = reddit.fullname(thing)
        query = 'SELECT * FROM {0} WHERE thing_fullname = ?'
        active = self._db.execute(query.format('active'), (fullname,))
        inactive = self._db.execute(query.format('inactive'), (fullname,))
        return bool(active.fetchone() or inactive.fetchone())

    @property
    def _create_table_data(self):
        columns = [
                'thing_fullname TEXT PRIMARY KEY NOT NULL',
                'created_utc REAL NOT NULL',
                'author_name TEXT NOT NULL COLLATE NOCASE',
                # store some optional data for debugging purposes
                # (eg. comment.permalink)
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
        from src import reddit

        self.__prune(thing)
        if hasattr(thing, 'author') and bool(thing.author):
            self._db.execute(
                    'INSERT INTO'
                    ' active(thing_fullname, created_utc, author_name, data)'
                    ' VALUES(?, ?, ?, ?)',
                    (
                        reddit.fullname(thing),
                        thing.created_utc,
                        thing.author.name,
                        data,
                    ),
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
                        'DELETE FROM active'
                        ' WHERE thing_fullname = ?'
                        ' AND created_utc = ?'
                        ' AND author_name = ?'
                        ' AND data = ?',
                        row,
                )
                try:
                    self._db.execute(
                            'INSERT INTO inactive'
                            '(thing_fullname, created_utc, author_name, data)'
                            ' VALUES(?, ?, ?, ?)',
                            row,
                    )
                except UniqueConstraintFailed:
                    # duplicate bad actor record entered
                    logger.id(logger.warn, self,
                            'Failed to move duplicate {color_thing}'
                            ' (by {color_author}) to inactive table!',
                            color_thing=row['thing_fullname'],
                            color_author=row['author_name'],
                            exc_info=True,
                    )

                pruned.append(row)

            if pruned:
                debug_rows = [
                        '{0}, {1}, {2}, {3}'.format(
                            row['thing_fullname'],
                            row['created_utc'],
                            row['author_name'],
                            row['data'],
                        ) for row in pruned
                ]
                logger.id(logger.debug, self,
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
        if hasattr(thing, 'author') and bool(thing.author):
            cursor = self._db.execute(
                    'SELECT created_utc FROM active WHERE author_name = ?',
                    (thing.author.name,),
            )
            return len(cursor.fetchall())
        return -1


__all__ = [
        'BadActorsDatabase',
]

