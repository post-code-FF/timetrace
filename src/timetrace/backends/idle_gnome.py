import time
from typing import Callable, Protocol


class MutterIdleDBusConnector(Protocol):
    def add_idle_watch(self, ms: int, callback: Callable[[], None]) -> int: ...
    def add_active_watch(self, callback: Callable[[], None]) -> int: ...
    def remove_watch(self, watch_id: int) -> None: ...


class QtMutterIdleDBusConnector:
    """Real connector over org.gnome.Mutter.IdleMonitor via QtDBus."""

    SERVICE = "org.gnome.Mutter.IdleMonitor"
    PATH = "/org/gnome/Mutter/IdleMonitor/Core"
    INTERFACE = "org.gnome.Mutter.IdleMonitor"

    def __init__(self) -> None:
        from PySide6.QtDBus import QDBusConnection, QDBusInterface

        self._bus = QDBusConnection.sessionBus()
        self._iface = QDBusInterface(self.SERVICE, self.PATH, self.INTERFACE, self._bus)
        self._callbacks: dict[int, Callable[[], None]] = {}

    def add_idle_watch(self, ms: int, callback: Callable[[], None]) -> int:
        reply = self._iface.call("AddIdleWatch", ms)
        watch_id = int(reply.arguments()[0])
        self._callbacks[watch_id] = callback
        self._bus.connect(
            self.SERVICE, self.PATH, self.INTERFACE, "WatchFired",
            self._on_watch_fired,
        )
        return watch_id

    def add_active_watch(self, callback: Callable[[], None]) -> int:
        reply = self._iface.call("AddUserActiveWatch")
        watch_id = int(reply.arguments()[0])
        self._callbacks[watch_id] = callback
        return watch_id

    def remove_watch(self, watch_id: int) -> None:
        self._iface.call("RemoveWatch", watch_id)
        self._callbacks.pop(watch_id, None)

    def _on_watch_fired(self, watch_id: int) -> None:
        callback = self._callbacks.get(watch_id)
        if callback:
            callback()


class MutterIdleMonitorBackend:
    def __init__(self, dbus_connector: MutterIdleDBusConnector | None = None) -> None:
        self._connector = dbus_connector or QtMutterIdleDBusConnector()
        self._threshold_ms = 0
        self._on_idle: Callable[[int], None] | None = None
        self._on_resume: Callable[[int], None] | None = None
        self._idle_watch_id: int | None = None
        self._active_watch_id: int | None = None

    def start(
        self,
        threshold_ms: int,
        on_idle: Callable[[int], None],
        on_resume: Callable[[int], None],
    ) -> None:
        self._threshold_ms = threshold_ms
        self._on_idle = on_idle
        self._on_resume = on_resume
        self._arm_idle_watch()

    def _arm_idle_watch(self) -> None:
        self._idle_watch_id = self._connector.add_idle_watch(self._threshold_ms, self._handle_idle)

    def _handle_idle(self) -> None:
        now_ts = int(time.time() * 1000)
        if self._on_idle:
            self._on_idle(now_ts)
        if self._idle_watch_id is not None:
            self._connector.remove_watch(self._idle_watch_id)
            self._idle_watch_id = None
        self._active_watch_id = self._connector.add_active_watch(self._handle_resume)

    def _handle_resume(self) -> None:
        now_ts = int(time.time() * 1000)
        if self._on_resume:
            self._on_resume(now_ts)
        if self._active_watch_id is not None:
            self._connector.remove_watch(self._active_watch_id)
            self._active_watch_id = None
        self._arm_idle_watch()

    def update_threshold(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms
        if self._idle_watch_id is not None:
            self._connector.remove_watch(self._idle_watch_id)
        self._arm_idle_watch()

    def stop(self) -> None:
        if self._idle_watch_id is not None:
            self._connector.remove_watch(self._idle_watch_id)
            self._idle_watch_id = None
        if self._active_watch_id is not None:
            self._connector.remove_watch(self._active_watch_id)
            self._active_watch_id = None
