"""Run via dbus-run-session; never claims org.gnome.Shell on the user's bus."""
import json
import os
import tempfile
import time
from pathlib import Path
from PySide6.QtCore import ClassInfo, QCoreApplication, QObject, QTimer, Slot
from PySide6.QtDBus import QDBusConnection
from timetrace.backends.session_gnome import GnomeSessionBackend, SERVICE, PATH, INTERFACE
from timetrace.backends.idle_base import NullIdleBackend
from timetrace.db import Store
from timetrace.tracking.coordinator import TrackingCoordinator

assert os.environ.get('TIMETRACE_PRIVATE_BUS_TEST') == '1'
app = QCoreApplication([])
bus = QDBusConnection.sessionBus()
assert bus.registerService(SERVICE)
base = int(time.time()*1000)
events = []

@ClassInfo(**{'D-Bus Interface': INTERFACE})
class Bridge(QObject):
    @Slot(str, result=str)
    def GetEvents(self, cursor):
        epoch, _, seq = cursor.partition(':')
        batch = [e for e in events if e['seq'] > int(seq or 0)] if epoch == 'test' else events[-1:]
        return json.dumps(dict(events=batch, overflow=False))

bridge = Bridge()
assert bus.registerObject(PATH, bridge, QDBusConnection.RegisterOption.ExportAllSlots)

def publish(rc, second, **kw):
    event = dict(version=1, epoch='test', seq=len(events)+1, ts=base+second*1000,
                 idle_ms=0, locked=False, available=True, app_id=rc, title='')
    event.update(kw)
    events.append(event)
    backend._poll()

backend = GnomeSessionBackend()
with tempfile.TemporaryDirectory() as temp:
    store = Store(Path(temp)/'data.db')
    coordinator = TrackingCoordinator(store, NullIdleBackend(), backend, 5000, clock=lambda: base)
    publish('terminal.desktop', 0)
    coordinator.start()
    timer = QTimer()
    timer.timeout.connect(coordinator.process_pending_events)
    timer.start(10)
    QTimer.singleShot(100, lambda: publish('firefox.desktop', 1))
    QTimer.singleShot(200, lambda: publish('', 2, locked=True))
    QTimer.singleShot(300, lambda: publish('editor.desktop', 3))
    QTimer.singleShot(400, lambda: publish('editor.desktop', 4, idle_ms=6000))
    QTimer.singleShot(500, lambda: publish('editor.desktop', 5))
    errors = []
    def finish():
        try:
            coordinator._clock = lambda: base+6000
            coordinator.stop()
            rows = store.app_intervals_for_day(0, base+100000, base+6000)
            actual = [(r.resource_class, r.end_ts-r.start_ts) for r in rows]
            expected = [('terminal.desktop', 1000), ('firefox.desktop', 1000),
                        ('editor.desktop', 1000), ('editor.desktop', 1000)]
            assert actual == expected, actual
            print('PASS: real private D-Bus -> Qt async -> GNOME backend -> coordinator -> SQLite')
            print(json.dumps(actual))
        except BaseException as exc:
            errors.append(exc)
        finally:
            store.close()
            app.quit()
    QTimer.singleShot(1000, finish)
    app.exec()
    if errors:
        raise errors[0]
