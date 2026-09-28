import re
import subprocess
import sys
import time
from typing import Callable, Protocol


class MutterIdleDBusConnector(Protocol):
    def add_idle_watch(self, ms: int, callback: Callable[[], None]) -> int: ...
    def add_active_watch(self, callback: Callable[[], None]) -> int: ...
    def remove_watch(self, watch_id: int) -> None: ...


_GDBUS_REPLY_UINT_RE = re.compile(r"\(\s*(\d+)\s*,?\s*\)")


class QtMutterIdleDBusConnector:
    """Real connector over org.gnome.Mutter.IdleMonitor.

    WatchFired notifications are received via QtDBus: that direction has no
    ambiguity, since Qt deserializes the already-typed value off the wire.
    Outgoing method calls, on the other hand, go through `gdbus call`
    (shipped with glib2, always present alongside GNOME Shell) instead of
    QDBusInterface.call(): PySide6 has no way to mark a plain Python int as
    unsigned when marshaling it, so it's always sent as D-Bus INT32 ('i').
    org.gnome.Mutter.IdleMonitor rejects that -- AddIdleWatch expects
    UINT64 ('t') and RemoveWatch expects UINT32 ('u') -- failing with e.g.
    "Message type '(i)' does not match expected type '(t)'". Confirmed
    against a live session bus (a 'u'-typed method call elsewhere) that
    QDBusInterface.call() with a plain int always marshals as 'i', and that
    `gdbus call`'s GVariant text format (e.g. "uint64 5000") is accepted.
    """

    SERVICE = "org.gnome.Mutter.IdleMonitor"
    PATH = "/org/gnome/Mutter/IdleMonitor/Core"
    INTERFACE = "org.gnome.Mutter.IdleMonitor"

    def __init__(self) -> None:
        from PySide6.QtCore import QObject, SLOT, Slot
        from PySide6.QtDBus import QDBusConnection

        self._bus = QDBusConnection.sessionBus()
        self._callbacks: dict[int, Callable[[], None]] = {}

        # QDBusConnection.connect() requires a QObject receiver plus a
        # Qt slot signature (built via SLOT()) — a plain Python callable
        # is not an accepted overload. Route the D-Bus signal to a tiny
        # QObject whose slot forwards to our real handler.
        outer = self

        class _WatchFiredReceiver(QObject):
            @Slot("uint")
            def on_watch_fired(self, watch_id: int) -> None:
                outer._on_watch_fired(watch_id)

        self._watch_fired_receiver = _WatchFiredReceiver()
        self._bus.connect(
            self.SERVICE, self.PATH, self.INTERFACE, "WatchFired",
            self._watch_fired_receiver, SLOT("on_watch_fired(uint)"),
        )

    def _call(self, method: str, *typed_args: str) -> str:
        result = subprocess.run(
            [
                "gdbus", "call", "--session",
                "--dest", self.SERVICE,
                "--object-path", self.PATH,
                "--method", f"{self.INTERFACE}.{method}",
                *typed_args,
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"{method} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    @staticmethod
    def _parse_reply_uint(gdbus_output: str, method_name: str) -> int:
        # gdbus prints a successful reply as a GVariant tuple literal, e.g. "(5,)".
        match = _GDBUS_REPLY_UINT_RE.match(gdbus_output)
        if not match:
            raise RuntimeError(f"{method_name}: unexpected gdbus reply {gdbus_output!r}")
        return int(match.group(1))

    def add_idle_watch(self, ms: int, callback: Callable[[], None]) -> int:
        output = self._call("AddIdleWatch", f"uint64 {ms}")
        watch_id = self._parse_reply_uint(output, "AddIdleWatch")
        self._callbacks[watch_id] = callback
        return watch_id

    def add_active_watch(self, callback: Callable[[], None]) -> int:
        output = self._call("AddUserActiveWatch")
        watch_id = self._parse_reply_uint(output, "AddUserActiveWatch")
        self._callbacks[watch_id] = callback
        return watch_id

    def remove_watch(self, watch_id: int) -> None:
        self._call("RemoveWatch", f"uint32 {watch_id}")
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
        # Re-arming happens outside the guarded start() call, driven later by
        # a fired watch -- an unhandled exception here would propagate out of
        # a Qt signal handler, which PySide/PyQt treats as fatal. Losing idle
        # tracking for the rest of the session beats crashing the whole app.
        try:
            self._idle_watch_id = self._connector.add_idle_watch(
                self._threshold_ms, self._handle_idle
            )
        except Exception as exc:
            print(f"timetrace: failed to re-arm idle watch, idle detection stopped: {exc}", file=sys.stderr)
            self._idle_watch_id = None

    def _handle_idle(self) -> None:
        now_ts = int(time.time() * 1000)
        if self._on_idle:
            self._on_idle(now_ts)
        if self._idle_watch_id is not None:
            self._connector.remove_watch(self._idle_watch_id)
            self._idle_watch_id = None
        try:
            self._active_watch_id = self._connector.add_active_watch(self._handle_resume)
        except Exception as exc:
            print(f"timetrace: failed to arm active watch, idle detection stopped: {exc}", file=sys.stderr)
            self._active_watch_id = None

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
        if self._active_watch_id is not None:
            return  # currently idle; new threshold applies next time an idle watch is armed
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
