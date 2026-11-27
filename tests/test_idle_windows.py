import sys

import pytest

from timetrace.backends.idle_windows import WindowsIdleBackend


class FakeInput:
    def __init__(self, tick=1000):
        self.tick = tick

    def last_input_tick(self):
        return self.tick

    def current_tick(self):
        return 2000


@pytest.mark.skipif(sys.platform != "win32", reason="Windows idle backend")
def test_idle_threshold_and_resume():
    source = FakeInput()
    backend = WindowsIdleBackend(input_source=source, poll_interval_s=0.01)
    events = []
    backend.start(500, lambda ts: events.append(("idle", ts)), lambda ts: events.append(("resume", ts)))
    try:
        assert events[-1][0] == "idle"
        source.tick = 1990
        backend._poll_once()
        assert events[-1][0] == "resume"
    finally:
        backend.stop()