import io
from pathlib import Path
import sqlite3
from contextlib import closing
import tarfile
import tempfile
import unittest
from tools.android_trip_backup import validate_backup

class BackupTest(unittest.TestCase):
    def test_database_rows_are_verified(self):
        with tempfile.TemporaryDirectory() as folder:
            dbfile=Path(folder)/'trips.db'
            with closing(sqlite3.connect(dbfile)) as db:
                db.executescript('CREATE TABLE trips(id TEXT); CREATE TABLE locations(id TEXT); INSERT INTO trips VALUES("keep"); INSERT INTO locations VALUES("keep"); PRAGMA user_version=2;'); db.commit()
            output=io.BytesIO()
            with tarfile.open(fileobj=output,mode='w') as archive: archive.add(dbfile,arcname='databases/trips.db')
            self.assertEqual(validate_backup(output.getvalue()),(1,1,2))
    def test_traversal_is_rejected(self):
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w') as archive: archive.addfile(tarfile.TarInfo('../escape'))
        with self.assertRaises(ValueError):validate_backup(output.getvalue())

if __name__=='__main__': unittest.main()
