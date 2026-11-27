import ctypes
from typing import Callable

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication
from PySide6.QtWidgets import QApplication

_WM_TIMETRACE_RAISE = 0x8001


class WindowsSingleInstance:
    def __init__(self, name: str = "TimeTrace.SingleInstance"):
        self._name = name
        self._mutex = None
        self._primary = False
        self._filter = None
        self._on_raise = None

    def acquire(self, on_raise: Callable[[], None]) -> bool:
        if self._mutex is not None:
            self._on_raise = on_raise
            return self._primary
        self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, self._name)
        self._primary = ctypes.windll.kernel32.GetLastError() != 183
        self._on_raise = on_raise
        if self._primary:
            outer = self

            class Filter(QAbstractNativeEventFilter):
                def nativeEventFilter(self, event_type, message):
                    if event_type == b"windows_generic_MSG":
                        msg = ctypes.wintypes.MSG.from_address(int(message))
                        if msg.message == _WM_TIMETRACE_RAISE and outer._on_raise:
                            outer._on_raise()
                    return False, 0

            self._filter = Filter()
            app = QApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self._filter)
        else:
            hwnd = ctypes.windll.user32.FindWindowW(None, "TimeTrace")
            if hwnd:
                ctypes.windll.user32.PostMessageW(hwnd, _WM_TIMETRACE_RAISE, 0, 0)
        return self._primary

    def release(self) -> None:
        app = QApplication.instance()
        if app is not None and self._filter is not None:
            app.removeNativeEventFilter(self._filter)
        self._filter = None
        if self._mutex:
            ctypes.windll.kernel32.CloseHandle(self._mutex)
            self._mutex = None