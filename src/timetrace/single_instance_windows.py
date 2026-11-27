import ctypes
from typing import Callable

from PySide6.QtCore import QCoreApplication, QEvent, QObject


class _RaiseEvent(QEvent):
    TYPE = QEvent.Type(QEvent.registerEventType())

    def __init__(self, callback: Callable[[], None]):
        super().__init__(self.TYPE)
        self.callback = callback


class _Receiver(QObject):
    def event(self, event):
        if isinstance(event, _RaiseEvent):
            event.callback()
            return True
        return super().event(event)


class WindowsSingleInstance:
    def __init__(self, name: str = "TimeTrace.SingleInstance"):
        self._name = name
        self._mutex = None
        self._primary = False
        self._receiver = None

    def acquire(self, on_raise: Callable[[], None]) -> bool:
        self._mutex = ctypes.windll.kernel32.CreateMutexW(None, False, self._name)
        self._primary = ctypes.windll.kernel32.GetLastError() != 183
        app = QCoreApplication.instance()
        if self._primary:
            if app is not None:
                self._receiver = _Receiver()
                app.installEventFilter(self._receiver)
        elif app is not None:
            QCoreApplication.postEvent(app, _RaiseEvent(on_raise))
        return self._primary

    def release(self) -> None:
        if self._mutex:
            ctypes.windll.kernel32.CloseHandle(self._mutex)
            self._mutex = None