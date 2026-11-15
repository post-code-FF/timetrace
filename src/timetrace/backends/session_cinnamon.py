"""Read-only snapshots using Cinnamon's built-in org.Cinnamon.Eval method.

No extension, schema changes or injected persistent handlers are needed.
"""
import json
import time

# Only constant read-only code is sent to Eval, never titles or user input.
SNAPSHOT_SCRIPT = """(() => {
    const Meta = imports.gi.Meta;
    const Cinnamon = imports.gi.Cinnamon;
    const Main = imports.ui.main;
    const w = global.display.get_focus_window();
    const app = w ? Cinnamon.WindowTracker.get_default().get_window_app(w) : null;
    const locked = Main.screensaverController
        ? Main.screensaverController.locked
        : global.settings.get_boolean('session-locked-state');
    return {app_id: w ? ((app && app.get_id()) || w.get_wm_class() || '') : '',
            title: w ? (w.get_title() || '') : '',
            fullscreen: !!(w && w.is_fullscreen()),
            idle_ms: Meta.IdleMonitor.get_core().get_idletime(), locked: !!locked};
})()"""


class CinnamonSessionBackend:
    def __init__(self):
        from PySide6.QtCore import QObject, QTimer
        from PySide6.QtDBus import QDBusConnection
        self._bus = QDBusConnection.sessionBus()
        self._owner = QObject()
        self._timer = QTimer(self._owner)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._poll)
        self._pending = None
        self._stopped = True
        self._window = self._presence = None
        self._threshold = 300_000
        self.extension_notice = None

    def start_presence_monitor(self, threshold_ms, callback):
        self._threshold = threshold_ms
        self._presence = callback

    def update_threshold(self, threshold_ms):
        self._threshold = threshold_ms

    def start(self, on_window_changed):
        self._window = on_window_changed
        self._stopped = False
        self._timer.start()
        self._poll()

    def _poll(self):
        if self._stopped or self._pending is not None:
            return
        from PySide6.QtDBus import QDBusMessage, QDBusPendingCallWatcher
        message = QDBusMessage.createMethodCall("org.Cinnamon", "/org/Cinnamon", "org.Cinnamon", "Eval")
        message.setArguments([SNAPSHOT_SCRIPT])
        watcher = QDBusPendingCallWatcher(self._bus.asyncCall(message, 1000), self._owner)
        self._pending = watcher
        watcher.finished.connect(self._reply)

    def _reply(self, watcher):
        from PySide6.QtDBus import QDBusMessage
        self._pending = None
        try:
            if self._stopped:
                return
            reply = watcher.reply()
            args = reply.arguments()
            if reply.type() == QDBusMessage.MessageType.ErrorMessage or len(args) != 2 or args[0] is not True:
                raise ValueError("Cinnamon snapshot unavailable")
            self._accept(json.loads(args[1]))
            self.extension_notice = None
        except Exception:
            self._unavailable()
        finally:
            watcher.deleteLater()

    def _accept(self, snapshot):
        if (not isinstance(snapshot, dict)
                or type(snapshot.get("idle_ms")) is not int or snapshot["idle_ms"] < 0
                or type(snapshot.get("locked")) is not bool
                or type(snapshot.get("fullscreen")) is not bool
                or not isinstance(snapshot.get("app_id"), str)
                or not isinstance(snapshot.get("title"), str)):
            raise ValueError("Invalid Cinnamon snapshot")
        ts = int(time.time() * 1000)
        blocked = snapshot["locked"]
        idle = not blocked and snapshot["idle_ms"] >= self._threshold and not snapshot["fullscreen"]
        if self._window:
            self._window(snapshot["app_id"] if not blocked else "", (snapshot["title"] or None) if not blocked else None, ts)
        if self._presence:
            self._presence(idle, blocked, ts)

    def _unavailable(self):
        self.extension_notice = "Cinnamon не предоставляет данные об окне или простое; учёт приостановлен."
        ts = int(time.time() * 1000)
        if self._window:
            self._window("", None, ts)
        if self._presence:
            self._presence(False, True, ts)

    def stop(self):
        self._stopped = True
        self._timer.stop()
        self._window = self._presence = None
