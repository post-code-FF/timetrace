"""Read-only compositor IPC, sampled at 500 ms without blocking the UI."""
import json
import logging
import os
import socket
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)


def _request(path: str, request: bytes, *, line: bool = False):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(1)
        sock.connect(path)
        sock.sendall(request)
        data = bytearray()
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > 4_000_000:
                raise ValueError("oversized compositor response")
            if line and b"\n" in data:
                break
        return json.loads(data)


class HyprlandReader:
    def __init__(self, path: str):
        self.path = path

    def __call__(self):
        window = _request(self.path, b"j/activewindow")
        mode = window.get("fullscreen", 0)
        # Hyprland's numeric enum: 1 is maximized, 2 is fullscreen. Preserve
        # boolean replies without treating maximization as an idle inhibitor.
        fullscreen = mode is True or (type(mode) is int and mode == 2)
        return (window.get("class") or "", window.get("title") or None,
                fullscreen)


class NiriReader:
    def __init__(self, path: str):
        self.path = path

    def __call__(self):
        reply = _request(self.path, b'"FocusedWindow"\n', line=True)
        if "Ok" not in reply or "FocusedWindow" not in reply["Ok"]:
            raise ValueError("niri did not return a focused-window snapshot")
        window = reply["Ok"]["FocusedWindow"] or {}
        # The niri Window IPC schema does not expose fullscreen state.
        return window.get("app_id") or "", window.get("title") or None, False


def compositor_reader(env=None):
    env = os.environ if env is None else env
    if env.get("NIRI_SOCKET"):
        return NiriReader(env["NIRI_SOCKET"])
    signature = env.get("HYPRLAND_INSTANCE_SIGNATURE")
    if signature:
        runtime = env.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        for directory in (Path(runtime) / "hypr" / signature, Path("/tmp/hypr") / signature):
            path = directory / ".socket.sock"
            if path.is_socket():
                return HyprlandReader(str(path))
    raise RuntimeError("No supported compositor IPC socket")


class PollingWindowBackend:
    def __init__(self, reader=None, interval=0.5):
        self._reader = reader or compositor_reader()
        self._interval = interval
        self._stop = threading.Event()
        self._thread = None
        self._fullscreen = None
        self.extension_notice = None

    def start_fullscreen_monitor(self, callback):
        self._fullscreen = callback

    def start(self, on_window_changed):
        self._stop.clear()

        def loop():
            previous = None
            while not self._stop.is_set():
                try:
                    snapshot = self._reader()
                    self.extension_notice = None
                except Exception:
                    snapshot = ("", None, False)
                    if self.extension_notice is None:
                        log.warning("Compositor IPC unavailable; foreground paused")
                    self.extension_notice = "Связь с оконным менеджером потеряна; учёт приложений приостановлен."
                if self._stop.is_set():
                    return
                if snapshot != previous:
                    ts = int(time.time() * 1000)
                    on_window_changed(snapshot[0], snapshot[1], ts)
                    if self._fullscreen:
                        self._fullscreen(snapshot[2], ts)
                    previous = snapshot
                self._stop.wait(self._interval)

        self._thread = threading.Thread(target=loop, daemon=True, name="timetrace-ipc")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
