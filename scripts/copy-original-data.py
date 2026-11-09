#!/usr/bin/env python3
"""Consistent SQLite backup from read-only original; refuse existing targets."""
import os
import sqlite3
from pathlib import Path
import time

base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
config = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
source = base / 'timetrace/data.db'
target = base / 'timetrace-gnome-fork/data.db'
if target.exists():
    raise SystemExit(f'Refusing to overwrite {target}')
if not source.is_file():
    raise SystemExit(f'Original database not found: {source}')
target.parent.mkdir(parents=True, exist_ok=True)
# Exclusive creation prevents overwrite even if another process races us.
fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
os.close(fd)
try:
    with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src:
        with sqlite3.connect(target) as dest:
            src.backup(dest)
            assert dest.execute('PRAGMA integrity_check').fetchone() == ('ok',)
            # Do not extend the original app's still-open intervals into test time.
            for table in ('presence_intervals', 'app_intervals'):
                dest.execute(f'UPDATE {table} SET end_ts=MAX(start_ts, ?) WHERE end_ts IS NULL', (int(time.time()*1000),))
    old_config = config / 'timetrace/config.toml'
    new_config = config / 'timetrace-gnome-fork/config.toml'
    if old_config.exists() and not new_config.exists():
        new_config.parent.mkdir(parents=True, exist_ok=True)
        # Copy theme and threshold but do not silently opt this fork into startup.
        text = old_config.read_text().replace('autostart = true', 'autostart = false')
        with new_config.open('x') as f:
            f.write(text)
except BaseException:
    target.unlink(missing_ok=True)
    raise
print(f'Copied database to {target}; original opened read-only')
