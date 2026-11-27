import ctypes
from typing import Callable

from timetrace.backends.win32_messages import MessageWindow, find_message_window, post_message

_WM_TIMETRACE_RAISE = 0x8001


class WindowsSingleInstance:
    def __init__(self, name: str = "TimeTrace.SingleInstance"):
        self._name = name
        self._mutex = None
        self._primary = False
        self._window = None
        self._on_raise = None

    def acquire(self, on_raise: Callable[[], None]) -> bool:
        if self._mutex is not None:
            self._on_raise = on_raise
            return self._primary
        self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, self._name)
        self._primary = ctypes.windll.kernel32.GetLastError() != 183
        self._on_raise = on_raise
        if self._primary:
            self._window = MessageWindow("TimeTrace", self._handle)
        else:
            hwnd = find_message_window("TimeTrace")
            if hwnd:
                post_message(hwnd, _WM_TIMETRACE_RAISE)
        return self._primary

    def _handle(self, msg: int, wparam: int, lparam: int) -> None:
        if msg == _WM_TIMETRACE_RAISE and self._on_raise:
            self._on_raise()

    def release(self) -> None:
        if self._window is not None:
            self._window.close()
            self._window = None
        if self._mutex:
            ctypes.windll.kernel32.CloseHandle(self._mutex)
            self._mutex = None