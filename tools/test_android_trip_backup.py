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

class MigrationRetentionTest(unittest.TestCase):
    def test_existing_trip_rows_survive_current_room_migration(self):
        import re
        source=(Path(__file__).resolve().parents[1]/'android/app/src/main/java/com/tripplanner/TripDatabase.kt').read_text()
        commands=re.findall(r'db\.execSQL\("([^"]+)"\)',source)
        self.assertEqual(len(commands),3)
        with closing(sqlite3.connect(':memory:')) as db:
            db.executescript('CREATE TABLE trips(id TEXT PRIMARY KEY,title TEXT,startId TEXT,endId TEXT); CREATE TABLE locations(id TEXT PRIMARY KEY,tripId TEXT,name TEXT,latitude REAL,longitude REAL); INSERT INTO trips VALUES("trip","Keep me","home","home"); INSERT INTO locations VALUES("home","trip","Home",32,35);')
            for command in commands: db.execute(command)
            self.assertEqual(db.execute('SELECT id,title,startId,endId,routeJson FROM trips').fetchone(),('trip','Keep me','home','home',None))
            self.assertEqual(db.execute('SELECT id,tripId,name,latitude,longitude,arrivalLatitude,arrivalLongitude FROM locations').fetchone(),('home','trip','Home',32,35,None,None))
