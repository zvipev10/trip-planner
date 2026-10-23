"""Back up/restore the local database of a USB-connected debuggable Trip Planner.

No uninstall or install is performed. Keep the backup private: it contains trips.
Usage: python tools/android_trip_backup.py backup trips-backup.tar
       python tools/android_trip_backup.py restore trips-backup.tar --replace-database
Requires Android platform-tools (adb), USB debugging, and device authorization.
"""
import argparse
import io
from pathlib import Path, PurePosixPath
import sqlite3
from contextlib import closing
import subprocess
import tarfile
import tempfile

PACKAGE = "com.tripplanner"

def validate_backup(data):
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            for member in archive.getmembers():
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'databases' or member.issym() or member.islnk() or not (member.isfile() or member.isdir()):
                    raise ValueError("Invalid database backup member")
                if member.size > 100_000_000:
                    raise ValueError("Database backup member is too large")
                target = root.joinpath(*path.parts)
                if member.isdir(): target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
        db_path = root/'databases'/'trips.db'
        if not db_path.is_file(): raise ValueError("Backup does not contain trips.db")
        with closing(sqlite3.connect(db_path)) as db:
            if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok': raise ValueError("Database integrity check failed")
            trips = db.execute('SELECT COUNT(*) FROM trips').fetchone()[0]
            places = db.execute('SELECT COUNT(*) FROM locations').fetchone()[0]
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (1, 2): raise ValueError("Unsupported database version")
        return trips, places, version

def adb(*args, **kwargs):
    return subprocess.run(['adb', *args], check=True, **kwargs)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['backup', 'restore'])
    parser.add_argument('file', type=Path)
    parser.add_argument('--replace-database', action='store_true')
    args = parser.parse_args()
    adb('get-state', capture_output=True)
    adb('shell', 'run-as', PACKAGE, 'id', capture_output=True)
    if args.action == 'backup':
        if args.file.exists(): parser.error('Backup file already exists; choose a new filename.')
        adb('shell', 'am', 'force-stop', PACKAGE)
        data = adb('exec-out', 'run-as', PACKAGE, 'tar', '-cf', '-', 'databases', capture_output=True).stdout
        counts = validate_backup(data)
        with args.file.open('xb') as output: output.write(data)
        print(f'Backup verified: {counts[0]} trips, {counts[1]} places, schema {counts[2]}. Saved to {args.file}')
    else:
        if not args.replace_database: parser.error('Restore replaces the installed database. First create a backup, then pass --replace-database.')
        data = args.file.read_bytes()
        counts = validate_backup(data)
        adb('shell', 'am', 'force-stop', PACKAGE)
        # Validate and stage before replacement; remove stale SQLite WAL files
        # so they cannot be replayed into the restored database.
        adb('shell', 'run-as', PACKAGE, 'rm', '-f', 'databases/trips.db-wal', 'databases/trips.db-shm')
        adb('shell', 'run-as', PACKAGE, 'tar', '-xf', '-', input=data)
        print(f'Restored {counts[0]} trips and {counts[1]} places. Open the app to apply its database migration.')

if __name__ == '__main__': main()
