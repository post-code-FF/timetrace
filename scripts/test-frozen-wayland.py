"""Check the packaged executable reaches SQLite from real native Wayland focus."""
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time

with tempfile.TemporaryDirectory() as directory:
    env = dict(os.environ, XDG_DATA_HOME=f"{directory}/data", XDG_CONFIG_HOME=f"{directory}/config")
    database = Path(env["XDG_DATA_HOME"]) / "timetrace/data.db"
    clients = []
    with open(f"{directory}/app.log", "w+") as log:
        app = subprocess.Popen([env["TIMETRACE_FROZEN_BIN"], "--minimized"], env=env, stdout=log, stderr=log)
        try:
            for ident in ("org.timetrace.FrozenFirst", "org.timetrace.FrozenSecond"):
                clients.append(subprocess.Popen(["foot", f"--app-id={ident}", "sleep", "60"]))
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    assert app.poll() is None, "packaged application exited"
                    if database.exists():
                        with sqlite3.connect(database) as connection:
                            rows = connection.execute("select resource_class from app_intervals").fetchall()
                        if (ident,) in rows:
                            break
                    time.sleep(0.1)
                else:
                    raise AssertionError(f"packaged application did not track {ident}")
            print('PASS: packaged launcher -> frozen Qt app -> native Wayland focus -> SQLite')
        except Exception:
            print({key: env.get(key) for key in ("WAYLAND_DISPLAY", "XDG_CURRENT_DESKTOP", "XDG_SESSION_TYPE", "QT_QPA_PLATFORM")})
            if database.exists():
                with sqlite3.connect(database) as connection:
                    print('recorded apps:', connection.execute("select * from app_intervals").fetchall())
                    print('presence:', connection.execute("select * from presence_intervals").fetchall())
            log.flush()
            log.seek(0)
            print(log.read())
            raise
        finally:
            app.terminate()
            app.wait(timeout=5)
            for client in clients:
                client.terminate()
                client.wait(timeout=3)
