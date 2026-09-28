import time
from typing import Callable, Protocol


class SleepDBusConnector(Protocol):
    def subscribe_prepare_for_sleep(self, callback: Callable[[bool], None]) -> None: ...
    def unsubscribe(self) -> None: ...


class QtLogindSleepConnector:
    """Real connector over org.freedesktop.login1.Manager.PrepareForSleep.

    This is systemd-logind's signal for suspend/resume: emitted with
    start=True right before the system suspends and start=False right
    after it resumes. Unlike the idle/active-window backends, this isn't
    desktop-environment-specific -- logind is the standard sleep-tracking
    mechanism on any systemd-based Linux, so there is no per-DE factory
    for this backend. It lives on the system bus, not the session bus.
    """

    SERVICE = "org.freedesktop.login1"
    PATH = "/org/freedesktop/login1"
    INTERFACE = "org.freedesktop.login1.Manager"

    def __init__(self) -> None:
        from PySide6.QtCore import QObject, SLOT, Slot
        from PySide6.QtDBus import QDBusConnection

        self._bus = QDBusConnection.systemBus()
        self._callback: Callable[[bool], None] | None = None

        outer = self

        class _PrepareForSleepReceiver(QObject):
            @Slot(bool)
            def on_prepare_for_sleep(self, start: bool) -> None:
                if outer._callback:
                    outer._callback(start)

        self._receiver = _PrepareForSleepReceiver()

    def subscribe_prepare_for_sleep(self, callback: Callable[[bool], None]) -> None:
        from PySide6.QtCore import SLOT

        self._callback = callback
        self._bus.connect(
            self.SERVICE, self.PATH, self.INTERFACE, "PrepareForSleep",
            self._receiver, SLOT("on_prepare_for_sleep(bool)"),
        )

    def unsubscribe(self) -> None:
        from PySide6.QtCore import SLOT

        self._bus.disconnect(
            self.SERVICE, self.PATH, self.INTERFACE, "PrepareForSleep",
            self._receiver, SLOT("on_prepare_for_sleep(bool)"),
        )


class SleepBackend(Protocol):
    def start(self, on_sleep: Callable[[int], None], on_wake: Callable[[int], None]) -> None: ...
    def stop(self) -> None: ...


class NullSleepMonitor:
    def start(self, on_sleep: Callable[[int], None], on_wake: Callable[[int], None]) -> None:
        pass

    def stop(self) -> None:
        pass


class SleepMonitor:
    def __init__(self, connector: SleepDBusConnector | None = None) -> None:
        self._connector = connector or QtLogindSleepConnector()

    def start(self, on_sleep: Callable[[int], None], on_wake: Callable[[int], None]) -> None:
        def handle(start: bool) -> None:
            ts = int(time.time() * 1000)
            if start:
                on_sleep(ts)
            else:
                on_wake(ts)

        self._connector.subscribe_prepare_for_sleep(handle)

    def stop(self) -> None:
        self._connector.unsubscribe()
