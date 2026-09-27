import time

from timetrace.backends.idle_base import NullIdleBackend
from timetrace.backends.idle_x11 import X11ScreenSaverIdleBackend


def test_null_backend_is_inert():
    b = NullIdleBackend()
    calls = []
    b.start(5000, lambda ts: calls.append(("idle", ts)), lambda ts: calls.append(("resume", ts)))
    b.update_threshold(1000)
    b.stop()
    assert calls == []


def test_x11_backend_fires_idle_and_resume_from_fake_reader():
    readings = iter([0, 0, 6000, 6000, 0])  # ms of idle time on each poll
    events = []

    def fake_query():
        return next(readings)

    backend = X11ScreenSaverIdleBackend(query_idle_ms=fake_query, poll_interval_s=0.01)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append(("idle", ts)),
        on_resume=lambda ts: events.append(("resume", ts)),
    )
    # let the poll loop consume all 5 fake readings
    deadline = time.monotonic() + 2.0
    while len(events) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    backend.stop()

    assert [kind for kind, _ in events] == ["idle", "resume"]


def test_x11_backend_update_threshold_takes_effect():
    readings = iter([2000, 2000, 2000])
    events = []

    def fake_query():
        return next(readings, 2000)

    backend = X11ScreenSaverIdleBackend(query_idle_ms=fake_query, poll_interval_s=0.01)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    time.sleep(0.05)
    backend.update_threshold(1000)  # now below the constant 2000ms reading
    deadline = time.monotonic() + 2.0
    while not events and time.monotonic() < deadline:
        time.sleep(0.02)
    backend.stop()

    assert events == ["idle"]
