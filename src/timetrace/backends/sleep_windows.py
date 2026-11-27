import time
from typing import Callable

from timetrace.backends.win32_messages import MessageWindow

_WM_POWERBROADCAST = 0x0218


class WindowsSleepMonitor:
    def __init__(self) -> None:
        self._window = None
        self._on_sleep = None
        self._on_wake = None

    def start(self, on_sleep: Callable[[int], None], on_wake: Callable[[int], None]) -> None:
        self._on_sleep = on_sleep
        self._on_wake = on_wake
        self._window = MessageWindow("TimeTraceSleep", self._handle)

    def _handle(self, msg: int, wparam: int, lparam: int) -> None:
        if msg != _WM_POWERBROADCAST:
            return
        ts = int(time.time() * 1000)
        if wparam in (0x0004, 0x000A):
            self._on_sleep(ts)
        elif wparam in (0x0012, 0x0007, 0x0008):
            self._on_wake(ts)

    def stop(self) -> None:
        if self._window is not None:
            self._window.close()
            self._window = None