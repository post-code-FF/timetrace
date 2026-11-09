#!/usr/bin/env python3
"""Live bridge -> coordinator -> separate SQLite integration recording."""
import argparse
import json
import logging
import resource
import time
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer
from timetrace.backends.session_gnome import GnomeSessionBackend
from timetrace.backends.idle_base import NullIdleBackend
from timetrace.backends.sleep_monitor import SleepMonitor
from timetrace.db import Store
from timetrace.tracking.coordinator import TrackingCoordinator

parser = argparse.ArgumentParser()
parser.add_argument('--seconds', type=int, default=120)
parser.add_argument('--idle-seconds', type=int, default=10)
parser.add_argument('--output', type=Path, required=True)
a = parser.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
db = a.output / 'probe.db'
if db.exists():
    parser.error(f'Refusing to reuse {db}')
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
app = QCoreApplication([])
store = Store(db)
backend = GnomeSessionBackend()
c = TrackingCoordinator(store, NullIdleBackend(), backend, a.idle_seconds*1000,
                        sleep_backend=SleepMonitor())
c.start()
tick = QTimer()
tick.timeout.connect(c.process_pending_events)
tick.start(50)
checkpoint = QTimer()
checkpoint.timeout.connect(c.checkpoint)
checkpoint.start(1000)
started = time.time()
cpu_start = time.process_time()

def finish():
    tick.stop()
    checkpoint.stop()
    c.stop()
    ended = int(time.time()*1000)
    rows = store.app_intervals_for_day(0, ended+1, ended)
    report = dict(
        elapsed_seconds=time.time()-started,
        process_cpu_seconds=time.process_time()-cpu_start,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        received_events=backend._stream.seq,
        foreground_intervals=[dict(app=r.resource_class, start=r.start_ts, end=r.end_ts,
                                   duration_ms=r.end_ts-r.start_ts) for r in rows],
        foreground_total_ms=sum(r.end_ts-r.start_ts for r in rows),
        presence=[dict(state=r.state, start=r.start_ts, end=r.end_ts)
                  for r in store.presence_intervals_for_day(0, ended+1, ended)],
    )
    (a.output / 'report.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2), flush=True)
    store.close()
    app.quit()

QTimer.singleShot(a.seconds*1000, finish)
raise SystemExit(app.exec())
