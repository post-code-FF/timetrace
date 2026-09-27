import time

from timetrace.backends.window_base import NullActiveWindowBackend
from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend


def test_null_backend_is_inert():
    b = NullActiveWindowBackend()
    calls = []
    b.start(lambda rc, title, ts: calls.append((rc, title, ts)))
    b.stop()
    assert calls == []


class FakeX11Client:
    def __init__(self, windows):
        # windows: list of (resource_class, title) to report on successive "changes"
        self._windows = iter(windows)
        self._current = None
        self._changes_remaining = len(windows)
        self.closed = False

    def wait_for_active_window_change(self, timeout_s):
        if self._changes_remaining <= 0:
            time.sleep(min(timeout_s, 0.02))
            return False
        self._changes_remaining -= 1
        self._current = next(self._windows)
        return True

    def get_active_window_info(self):
        return self._current

    def close(self):
        self.closed = True


def test_reports_each_window_change():
    client = FakeX11Client([("firefox", "Mozilla Firefox"), ("code", "Visual Studio Code")])
    events = []
    backend = X11EwmhActiveWindowBackend(xlib_client=client)
    backend.start(lambda rc, title, ts: events.append((rc, title)))

    deadline = time.monotonic() + 2.0
    while len(events) < 2 and time.monotonic() < deadline:
        time.sleep(0.02)
    backend.stop()

    assert events == [("firefox", "Mozilla Firefox"), ("code", "Visual Studio Code")]
    assert client.closed is True


def test_stop_closes_client_and_halts_thread():
    client = FakeX11Client([("firefox", "Mozilla Firefox")])
    backend = X11EwmhActiveWindowBackend(xlib_client=client)
    backend.start(lambda rc, title, ts: None)
    time.sleep(0.05)
    backend.stop()
    assert client.closed is True
