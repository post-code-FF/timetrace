import sys
import time

import pytest

from timetrace.backends.window_windows import WindowsActiveWindowBackend


class FakeWin32:
    def __init__(self):
        self.info = ("chrome.exe", "Документы — Chrome")
        self.fullscreen = False
        self.closed = False

    def get_active_window_info(self):
        return self.info

    def get_active_window_fullscreen(self):
        return self.fullscreen

    def close(self):
        self.closed = True


@pytest.mark.skipif(sys.platform != "win32", reason="Windows active-window backend")
def test_window_backend_emits_focus_and_fullscreen_changes():
    client = FakeWin32()
    backend = WindowsActiveWindowBackend(client=client, poll_interval_s=0.01)
    windows = []
    fullscreen = []
    backend.start_fullscreen_monitor(lambda value, ts: fullscreen.append((value, ts)))
    backend.start(lambda rc, title, ts: windows.append((rc, title, ts)))
    try:
        deadline = time.monotonic() + 1
        while not windows and time.monotonic() < deadline:
            time.sleep(0.01)
        assert windows[0][:2] == ("chrome.exe", "Документы — Chrome")
        client.info = ("notepad.exe", "Без имени — Блокнот")
        client.fullscreen = True
        deadline = time.monotonic() + 1
        while len(windows) < 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert windows[1][:2] == ("notepad.exe", "Без имени — Блокнот")
        assert fullscreen[-1][0] is True
    finally:
        backend.stop()
    assert client.closed


@pytest.mark.skipif(sys.platform != "win32", reason="Windows active-window backend")
def test_window_backend_reports_no_foreground_window():
    client = FakeWin32()
    client.info = None
    backend = WindowsActiveWindowBackend(client=client, poll_interval_s=0.01)
    events = []
    backend.start(lambda rc, title, ts: events.append((rc, title, ts)))
    try:
        deadline = time.monotonic() + 1
        while not events and time.monotonic() < deadline:
            time.sleep(0.01)
        assert events[0][:2] == ("", None)
    finally:
        backend.stop()