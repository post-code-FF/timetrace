"""Versioned, read-only GNOME Shell bridge; persistent Qt D-Bus connection.

The extension is explicitly installed by scripts/install-extension.sh. Starting
TimeTrace never rewrites or enables extensions. Snapshot replay covers notification
loss; an unavailable bridge fails closed rather than charging stale foreground.
"""
import json
import logging
import time
from collections.abc import Callable

log = logging.getLogger(__name__)
SERVICE = "org.gnome.Shell"
PATH = "/org/timetrace/GnomeFork/Bridge"
INTERFACE = "org.timetrace.GnomeFork.Bridge1"


class EventStream:
    """Validate and deduplicate the versioned stream independently of Qt."""
    def __init__(self):
        self.epoch = ""
        self.seq = 0
        self.last_ts = 0

    @property
    def cursor(self):
        return f"{self.epoch}:{self.seq}"

    def decode(self, payload: str):
        if len(payload) > 4_000_000:
            raise ValueError("oversized bridge response")
        packet = json.loads(payload)
        events = packet["events"]
        if not isinstance(events, list) or len(events) > 600:
            raise ValueError("invalid event batch")
        if packet.get("overflow"):
            log.warning("GNOME history overflow: unobserved intervals will remain untracked")
            events = events[-1:]
        for e in events:
            if (e.get("version") != 1 or not isinstance(e.get("epoch"), str)
                    or type(e.get("seq")) is not int or type(e.get("ts")) is not int
                    or type(e.get("idle_ms")) is not int
                    or type(e.get("locked")) is not bool or type(e.get("available")) is not bool
                    or not isinstance(e.get("app_id"), str)
                    or not isinstance(e.get("title"), str)):
                raise ValueError("invalid GNOME event")
            if e["epoch"] == self.epoch and e["seq"] <= self.seq:
                continue
            if e["seq"] < 1 or e["ts"] < 0:
                raise ValueError("invalid event sequence/timestamp")
            gap = bool(self.epoch) and (packet.get("overflow") or e["epoch"] != self.epoch)
            previous_ts = self.last_ts
            self.epoch, self.seq = e["epoch"], e["seq"]
            self.last_ts = max(self.last_ts, e["ts"])
            yield dict(e, ts=self.last_ts, gap_since=previous_ts if gap else None)


class GnomeSessionBackend:
    def __init__(self):
        from PySide6.QtCore import QObject, QTimer, SLOT, Slot
        from PySide6.QtDBus import QDBusConnection
        self._bus = QDBusConnection.sessionBus()
        self._stream = EventStream()
        self._connection_name = None
        self._last_seen = time.monotonic()
        self._window = None
        self._presence = None
        self._threshold = 300_000
        self._pending = None
        self._stopped = True
        self._unavailable = False
        self._last_state = None
        outer = self

        class Receiver(QObject):
            @Slot()
            def changed(self):
                outer._poll()

        self._receiver = Receiver()
        self._slot = SLOT("changed()")
        self._timer = QTimer(self._receiver)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._poll)

    def start_presence_monitor(self, threshold_ms: int, callback: Callable):
        self._threshold = threshold_ms
        self._presence = callback

    def update_threshold(self, threshold_ms: int):
        self._threshold = threshold_ms
        self._last_state = None
        self._poll()

    def start(self, on_window_changed):
        self._window = on_window_changed
        self._stopped = False
        if not self._bus.connect(SERVICE, PATH, INTERFACE, "Changed", self._receiver, self._slot):
            log.warning("GNOME D-Bus signal subscription failed; using snapshot polling")
        self._timer.start()
        self._poll()

    def _poll(self):
        if self._stopped or self._pending is not None:
            return
        from PySide6.QtDBus import QDBusConnection, QDBusMessage, QDBusPendingCallWatcher
        if not self._bus.isConnected():
            if self._connection_name:
                QDBusConnection.disconnectFromBus(self._connection_name)
            self._connection_name = f"timetrace-gnome-fork-{id(self)}"
            self._bus = QDBusConnection.connectToBus(
                QDBusConnection.BusType.SessionBus, self._connection_name)
            self._bus.connect(SERVICE, PATH, INTERFACE, "Changed", self._receiver, self._slot)
        msg = QDBusMessage.createMethodCall(SERVICE, PATH, INTERFACE, "GetEvents")
        msg.setArguments([self._stream.cursor])
        watcher = QDBusPendingCallWatcher(self._bus.asyncCall(msg, 1500), self._receiver)
        self._pending = watcher
        watcher.finished.connect(self._reply)

    def _reply(self, watcher):
        from PySide6.QtDBus import QDBusMessage
        self._pending = None
        try:
            if self._stopped:
                return
            reply = watcher.reply()
            if reply.type() == QDBusMessage.MessageType.ErrorMessage:
                raise RuntimeError(f"{reply.errorName()}: {reply.errorMessage()}")
            for e in self._stream.decode(reply.arguments()[0]):
                self._accept(e)
                self._last_seen = time.monotonic()
            if time.monotonic() - self._last_seen > 3:
                raise RuntimeError("GNOME heartbeat expired")
            self._unavailable = False
        except Exception as exc:
            if not self._unavailable:
                log.warning("GNOME bridge unavailable: %s; foreground paused", exc)
                self._unavailable = True
                ts = self._stream.last_ts or int(time.time() * 1000)
                self._stream.last_ts = ts
                self._last_state = None
                if self._presence:
                    self._presence(False, True, ts)
                if self._window:
                    self._window("", None, ts)
        finally:
            watcher.deleteLater()

    def _accept(self, e):
        if e.get("gap_since") is not None:
            if self._presence:
                self._presence(False, True, e["gap_since"])
            if self._window:
                self._window("", None, e["gap_since"])
            self._last_state = None
        # Idle API returning -1 means unsupported, not active. Fail closed.
        blocked = not e["available"] or e["locked"] or e["idle_ms"] < 0
        idle = e["idle_ms"] >= self._threshold
        state = (blocked, idle)
        # Queue focus first; coordinator's gate handles blocked transitions.
        if self._window:
            self._window(e["app_id"] if not blocked else "", e["title"] or None, e["ts"])
        if state != self._last_state and self._presence:
            self._presence(idle, blocked, e["ts"])
        self._last_state = state
        # Deliberately omit window titles from logs.
        log.debug("GNOME seq=%s app=%r idle=%s blocked=%s ts=%s",
                  e["seq"], e["app_id"], idle, blocked, e["ts"])

    def stop(self):
        self._stopped = True
        self._timer.stop()
        self._bus.disconnect(SERVICE, PATH, INTERFACE, "Changed", self._receiver, self._slot)
        self._window = self._presence = None
        if self._connection_name:
            from PySide6.QtDBus import QDBusConnection
            QDBusConnection.disconnectFromBus(self._connection_name)
            self._connection_name = None
