import os
import sqlite3
import subprocess
import sys
from pathlib import Path


def test_data_copy_preserves_original_bytes_and_refuses_overwrite(tmp_path):
    root = Path(__file__).resolve().parents[1]
    data = tmp_path/'data'
    config = tmp_path/'config'
    original = data/'timetrace/data.db'
    original.parent.mkdir(parents=True)
    with sqlite3.connect(original) as conn:
        conn.executescript('CREATE TABLE app_intervals (id INTEGER PRIMARY KEY, resource_class TEXT, window_title TEXT, start_ts INTEGER, end_ts INTEGER); CREATE TABLE presence_intervals (id INTEGER PRIMARY KEY, state TEXT, start_ts INTEGER, end_ts INTEGER);')
        conn.execute("INSERT INTO app_intervals VALUES (1,'editor',NULL,1000,2000)")
        conn.execute("INSERT INTO presence_intervals VALUES (1,'active',1000,NULL)")
    original_config = config/'timetrace/config.toml'
    original_config.parent.mkdir(parents=True)
    original_config.write_text('autostart = true\nidle_threshold_minutes = 5\ntheme = "dark"\n')
    before = original.read_bytes()
    env = dict(os.environ, XDG_DATA_HOME=str(data), XDG_CONFIG_HOME=str(config))
    command = [sys.executable, str(root/'scripts/copy-original-data.py')]
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert original.read_bytes() == before
    assert original_config.read_text().startswith('autostart = true')
    target = data/'timetrace-gnome-fork/data.db'
    with sqlite3.connect(target) as conn:
        assert conn.execute('SELECT resource_class,start_ts,end_ts FROM app_intervals').fetchall() == [('editor',1000,2000)]
        assert conn.execute('SELECT end_ts FROM presence_intervals').fetchone()[0] is not None
    copied_bytes = target.read_bytes()
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Refusing' in result.stderr
    assert target.read_bytes() == copied_bytes
