"""Consistent SQLite backup, including committed WAL contents."""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

os.umask(0o077)
source = Path(os.environ.get('DATABASE_PATH', '/var/lib/alien-invasion/game.sqlite3'))
if not source.is_file():
    raise SystemExit('Database does not exist')
directory = source.parent / 'backups'
directory.mkdir(exist_ok=True, mode=0o700)
destination = directory / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite3')
with sqlite3.connect(source) as origin, sqlite3.connect(destination) as target:
    origin.backup(target)
    if target.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
        raise RuntimeError('Backup integrity check failed')
for old in sorted(directory.glob('*.sqlite3'))[:-14]:
    old.unlink()
print(destination)
