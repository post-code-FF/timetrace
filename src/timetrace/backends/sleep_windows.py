import ctypes
import time
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter


class WindowsSleepMonitor:
    def __init__(self) -> None:
        self._filter = None
        self._on_sleep = None
        self._on_wake = None

    def start(self, on_sleep: Callable[[int], None], on_wake: Callable[[int], None]) -> None:
        from PySide6.QtWidgets import QApplication
        self._on_sleep = on_sleep
        self._on_wake = on_wake
        outer = self

        class Filter(QAbstractNativeEventFilter):
            def nativeEventFilter(self, event_type, message):
                if event_type == b"windows_generic_MSG":
                    msg = ctypes.wintypes.MSG.from_address(int(message))
                    if msg.message == 0x0218:
                        ts = int(time.time() * 1000)
                        if msg.wParam in (0x0004, 0x000A):
                            outer._on_sleep(ts)
                        elif msg.wParam in (0x0012, 0x0007, 0x0008):
                            outer._on_wake(ts)
                return False, 0

        self._filter = Filter()
        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self._filter)

    def stop(self) -> None:
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None and self._filter is not None:
            app.removeNativeEventFilter(self._filter)
        self._filter = None