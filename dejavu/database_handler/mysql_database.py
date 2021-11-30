import mysql.connector
from mysql.connector.errors import DatabaseError

from dejavu.base_classes.common_database import CommonDatabase
from dejavu.config.settings import (FIELD_FILE_SHA1, FIELD_FINGERPRINTED,
                                    FIELD_HASH, FIELD_OFFSET, FIELD_SONG_ID,
                                    FIELD_SONGNAME, FIELD_TOTAL_HASHES, FIELD_PUBLISHER, FIELD_SONG_LENGTH,
                                    FIELD_SINGER, FIELD_ALBUM, FIELD_PUBLICTIME,
                                    FINGERPRINTS_TABLENAME, SONGS_TABLENAME)

from dejavu.third_party.dejavu_timer import DejavuTimer


class MySQLDatabase(CommonDatabase):
    type = "mysql"

    # CREATES
    CREATE_SONGS_TABLE = f"""
        CREATE TABLE IF NOT EXISTS `{SONGS_TABLENAME}` (
            `{FIELD_SONG_ID}` MEDIUMINT UNSIGNED NOT NULL AUTO_INCREMENT
        ,   `{FIELD_SONGNAME}` VARCHAR(250) NOT NULL
        ,   `{FIELD_FINGERPRINTED}` TINYINT DEFAULT 0
        ,   `{FIELD_FILE_SHA1}` BINARY(20) NOT NULL
        ,   `{FIELD_TOTAL_HASHES}` INT NOT NULL DEFAULT 0
        ,   `{FIELD_PUBLISHER}` VARCHAR(64) DEFAULT 'Unknown'
        ,   `{FIELD_SONG_LENGTH}` FLOAT DEFAULT 0
        ,   `{FIELD_SINGER}` VARCHAR(64) DEFAULT 'Unknown'
        ,   `{FIELD_ALBUM}` VARCHAR(64) DEFAULT 'Unknown'
        ,   `{FIELD_PUBLICTIME}` VARCHAR(64) DEFAULT 'Unknown'
        ,   `date_created` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ,   `date_modified` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ,   CONSTRAINT `pk_{SONGS_TABLENAME}_{FIELD_SONG_ID}` PRIMARY KEY (`{FIELD_SONG_ID}`)
        ,   CONSTRAINT `uq_{SONGS_TABLENAME}_{FIELD_SONG_ID}` UNIQUE KEY (`{FIELD_SONG_ID}`)
        ) ENGINE=INNODB;
    """

    CREATE_FINGERPRINTS_TABLE = f"""
        CREATE TABLE IF NOT EXISTS `{FINGERPRINTS_TABLENAME}` (
            `{FIELD_HASH}` BINARY(10) NOT NULL
        ,   `{FIELD_SONG_ID}` MEDIUMINT UNSIGNED NOT NULL
        ,   `{FIELD_OFFSET}` INT UNSIGNED NOT NULL
        ,   `date_created` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ,   `date_modified` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ,   INDEX `ix_{FINGERPRINTS_TABLENAME}_{FIELD_HASH}` (`{FIELD_HASH}`)
        ,   CONSTRAINT `uq_{FINGERPRINTS_TABLENAME}_{FIELD_SONG_ID}_{FIELD_OFFSET}_{FIELD_HASH}`
                UNIQUE KEY  (`{FIELD_SONG_ID}`, `{FIELD_OFFSET}`, `{FIELD_HASH}`)
        ,   CONSTRAINT `fk_{FINGERPRINTS_TABLENAME}_{FIELD_SONG_ID}` FOREIGN KEY (`{FIELD_SONG_ID}`)
                REFERENCES `{SONGS_TABLENAME}`(`{FIELD_SONG_ID}`) ON DELETE CASCADE
    ) ENGINE=INNODB;
    """

    # INSERTS (IGNORES DUPLICATES)
    INSERT_FINGERPRINT = f"""
        INSERT IGNORE INTO `{FINGERPRINTS_TABLENAME}` (
                `{FIELD_SONG_ID}`
            ,   `{FIELD_HASH}`
            ,   `{FIELD_OFFSET}`)
        VALUES (%s, UNHEX(%s), %s);
    """

    INSERT_SONG = f"""
        INSERT INTO `{SONGS_TABLENAME}` (`{FIELD_SONGNAME}`,`{FIELD_FILE_SHA1}`,`{FIELD_TOTAL_HASHES}`,
            `{FIELD_PUBLISHER}`,`{FIELD_SONG_LENGTH}`,`{FIELD_SINGER}`,`{FIELD_ALBUM}`,`{FIELD_PUBLICTIME}`)
        VALUES (%s, UNHEX(%s), %s, %s, %s, %s, %s, %s);
    """

    # SELECTS
    SELECT = f"""
        SELECT `{FIELD_SONG_ID}`, `{FIELD_OFFSET}`
        FROM `{FINGERPRINTS_TABLENAME}`
        WHERE `{FIELD_HASH}` = UNHEX(%s);
    """

    SELECT_MULTIPLE = f"""
        SELECT HEX(`{FIELD_HASH}`), `{FIELD_SONG_ID}`, `{FIELD_OFFSET}`
        FROM `{FINGERPRINTS_TABLENAME}`
        WHERE `{FIELD_HASH}` IN (%s);
    """

    SELECT_ALL = f"SELECT `{FIELD_SONG_ID}`, `{FIELD_OFFSET}` FROM `{FINGERPRINTS_TABLENAME}`;"

    SELECT_SONG = f"""
        SELECT `{FIELD_SONGNAME}`, `{FIELD_PUBLISHER}`, `{FIELD_SONG_LENGTH}`, `{FIELD_SINGER}`, `{FIELD_ALBUM}`,
        `{FIELD_PUBLICTIME}`, HEX(`{FIELD_FILE_SHA1}`) AS `{FIELD_FILE_SHA1}`, `{FIELD_TOTAL_HASHES}`
        FROM `{SONGS_TABLENAME}`
        WHERE `{FIELD_SONG_ID}` = %s;
    """

    SELECT_SONGS_BY_IDS = f"""
        SELECT `{FIELD_SONG_ID}`, `{FIELD_SONGNAME}`, `{FIELD_PUBLISHER}`, `{FIELD_SONG_LENGTH}`, `{FIELD_SINGER}`, 
            `{FIELD_ALBUM}`, `{FIELD_PUBLICTIME}`, HEX(`{FIELD_FILE_SHA1}`) AS `{FIELD_FILE_SHA1}`, 
            `{FIELD_TOTAL_HASHES}`
        FROM `{SONGS_TABLENAME}`
        WHERE `{FIELD_SONG_ID}` IN (%s);
    """

    SELECT_NUM_FINGERPRINTS = f"SELECT COUNT(*) AS n FROM `{FINGERPRINTS_TABLENAME}`;"

    SELECT_UNIQUE_SONG_IDS = f"""
        SELECT COUNT(`{FIELD_SONG_ID}`) AS n
        FROM `{SONGS_TABLENAME}`
        WHERE `{FIELD_FINGERPRINTED}` = 1;
    """

    SELECT_SONGS = f"""
        SELECT
            `{FIELD_SONG_ID}`
        ,   `{FIELD_SONGNAME}`
        ,   `{FIELD_PUBLISHER}`
        ,   `{FIELD_SONG_LENGTH}`
        ,   `{FIELD_SINGER}`
        ,   `{FIELD_ALBUM}`
        ,   `{FIELD_PUBLICTIME}`
        ,   HEX(`{FIELD_FILE_SHA1}`) AS `{FIELD_FILE_SHA1}`
        ,   `{FIELD_TOTAL_HASHES}`
        ,   `date_created`
        FROM `{SONGS_TABLENAME}`
        WHERE `{FIELD_FINGERPRINTED}` = 1;
    """
    # !!          AND `{FIELD_PUBLISHER}` = %s;

    # DROPS
    DROP_FINGERPRINTS = f"DROP TABLE IF EXISTS `{FINGERPRINTS_TABLENAME}`;"
    DROP_SONGS = f"DROP TABLE IF EXISTS `{SONGS_TABLENAME}`;"

    # UPDATE
    UPDATE_SONG_FINGERPRINTED = f"""
        UPDATE `{SONGS_TABLENAME}` SET `{FIELD_FINGERPRINTED}` = 1 WHERE `{FIELD_SONG_ID}` = %s;
    """

    # DELETES
    DELETE_UNFINGERPRINTED = f"""
        DELETE FROM `{SONGS_TABLENAME}` WHERE `{FIELD_FINGERPRINTED}` = 0;
    """

    DELETE_SONGS = f"""
        DELETE FROM `{SONGS_TABLENAME}` WHERE `{FIELD_SONG_ID}` IN (%s);
    """

    # IN
    IN_MATCH = f"UNHEX(%s)"

    def __init__(self, **options):
        super().__init__()
        self.cursor = cursor_factory(**options)
        self._options = options

    def after_fork(self) -> None:
        # Clear the cursor cache, we don't want any stale connections from
        # the previous process.
        Cursor.clear_cache()

    def insert_song(self, song_name: str, file_hash: str, total_hashes: int, song_publisher: str = '',
                    song_length: float = 0, song_singer: str = '', song_album: str = '', song_public: str = '') -> int:
        """
        Inserts a song name into the database, returns the new
        identifier of the song.

        :param song_name: The name of the song.
        :param file_hash: Hash from the fingerprinted file.
        :param total_hashes: amount of hashes to be inserted on fingerprint table.
        :param song_publisher: The publisher of the song.
        :param song_length: The length of the song.
        :param song_singer: The singer of the song.
        :param song_album: The album of the song.
        :param song_public: The public time of the song.
        :return: the inserted id.
        """
        with self.cursor() as cur:
            cur.execute(self.INSERT_SONG, (song_name, file_hash, total_hashes, song_publisher, song_length, song_singer,
                                           song_album, song_public))
            return cur.lastrowid

    def __getstate__(self):
        return self._options,

    def __setstate__(self, state):
        self._options, = state
        self.cursor = cursor_factory(**self._options)


def cursor_factory(**factory_options):
    def cursor(**options):
        options.update(factory_options)
        return Cursor(**options)
    return cursor


class Cursor(object):
    """
    Establishes a connection to the database and returns an open cursor.
    # Use as context manager
    with Cursor() as cur:
        cur.execute(query)
        ...
    """

    @DejavuTimer(name=__name__ + ".Cursor.__init__()\t\t[agg]")
    def __init__(self, dictionary=False, **options):
        super().__init__()
        #  https://dev.mysql.com/doc/connector-python/en/connector-python-connection-pooling.html
        options.update({'pool_name': "dejavu-pool", 'pool_size': 1})
        self.conn = mysql.connector.connect(**options)  # Cursor._conn
        self.dictionary = dictionary

    def __enter__(self):
        self.cursor = self.conn.cursor(dictionary=self.dictionary)
        return self

    @DejavuTimer(name=__name__ + ".Cursor.execute()\t\t\t[agg]")
    def execute(self, operation, params=(), multi=False):
        return self.cursor.execute(operation, params, multi)

    def executemany(self, operation, seq_params):
        return self.cursor.executemany(operation, seq_params)

    @DejavuTimer(name=__name__ + ".Cursor.fetchone()\t\t[agg]")
    def fetchone(self):
        return self.cursor.fetchone()

    @DejavuTimer(name=__name__ + ".Cursor.fetchall()\t\t")
    def fetchall(self):
        return self.cursor.fetchall()

    @property
    def lastrowid(self):
        return self.cursor.lastrowid

    def __iter__(self):
        return self.cursor.__iter__()

    def __next__(self):
        return self.cursor.__next__()

    def __exit__(self, extype, exvalue, traceback):
        # if we had a MySQL related error we try to rollback the cursor.
        if extype is DatabaseError:
            self.cursor.rollback()

        self.cursor.close()
        self.conn.commit()
        self.conn.close()
