"""Capability-based foreign-toplevel tracking (wlroots and COSMIC)."""
import logging
import select
import struct
import threading
import time

from timetrace.backends.wayland_connection import roundtrip

log = logging.getLogger(__name__)


class ToplevelTracker:
    def __init__(self, callback):
        self.callback = callback
        self.windows = {}
        self.pending = {}
        self.active = None

    def add(self, handle):
        self.windows[handle] = dict(app_id="", title=None, activated=False, fullscreen=False)
        self.pending[handle] = self.windows[handle].copy()

    def update(self, handle, **properties):
        if handle not in self.windows:
            return
        states = properties.pop("states", None)
        if states is not None:
            raw = bytes(states)
            values = {value[0] for value in struct.iter_unpack("=I", raw)}
            properties.update(activated=2 in values, fullscreen=3 in values)
        self.pending[handle].update(properties)

    def commit(self, handle):
        window = self.pending.get(handle)
        if window is None:
            return
        self.windows[handle] = window.copy()
        if window["activated"]:
            self.active = handle
        elif self.active == handle:
            self.active = None
        self.publish()

    def commit_all(self):
        self.windows = {handle: window.copy() for handle, window in self.pending.items()}
        self.active = next((handle for handle, window in self.windows.items()
                            if window["activated"]), None)
        self.publish()

    def commit_metadata(self, handle):
        if handle in self.windows:
            for key in ("app_id", "title"):
                self.windows[handle][key] = self.pending[handle][key]
            self.publish()

    def close(self, handle):
        self.windows.pop(handle, None)
        self.pending.pop(handle, None)
        if self.active == handle:
            self.active = None
            self.publish()

    def publish(self):
        window = self.windows.get(self.active)
        if window is None:
            self.callback("", None, False)
        else:
            self.callback(window["app_id"], window["title"] or None, window["fullscreen"])

    def clear(self):
        self.windows.clear()
        self.pending.clear()
        self.active = None
        self.publish()


class WaylandToplevelClient:
    def __init__(self):
        from pywayland.client import Display
        from timetrace._wayland_protocols.wlr_foreign_toplevel_management_unstable_v1 import ZwlrForeignToplevelManagerV1
        from timetrace._wayland_protocols.cosmic_toplevel_info_unstable_v1 import ZcosmicToplevelInfoV1
        from timetrace._wayland_protocols.ext_foreign_toplevel_list_v1 import ExtForeignToplevelListV1

        self.tracker = ToplevelTracker(lambda *args: None)
        self.alive = True
        self._extensions = {}
        self.display = Display()
        self.display.connect()
        self.registry = self.display.get_registry()
        globals_ = {}
        self.registry.dispatcher["global"] = lambda registry, name, interface, version: globals_.update({interface: (name, version)})
        try:
            roundtrip(self.display)
            if ZwlrForeignToplevelManagerV1.name in globals_:
                name, version = globals_[ZwlrForeignToplevelManagerV1.name]
                self.manager = self.registry.bind(name, ZwlrForeignToplevelManagerV1, min(version, 3))
                self.manager.dispatcher["toplevel"] = self._wlr_toplevel
                self.manager.dispatcher["finished"] = self._finished
            elif (ZcosmicToplevelInfoV1.name in globals_ and ExtForeignToplevelListV1.name in globals_
                  and globals_[ZcosmicToplevelInfoV1.name][1] >= 2):
                name, _ = globals_[ZcosmicToplevelInfoV1.name]
                self.info = self.registry.bind(name, ZcosmicToplevelInfoV1, 2)
                self.info.dispatcher["done"] = lambda info: self.tracker.commit_all()
                name, version = globals_[ExtForeignToplevelListV1.name]
                self.manager = self.registry.bind(name, ExtForeignToplevelListV1, 1)
                self.manager.dispatcher["toplevel"] = self._cosmic_toplevel
                self.manager.dispatcher["finished"] = self._finished
            else:
                raise RuntimeError("No foreign-toplevel protocol with activation state")
            manager_id = name
            self.registry.dispatcher["global_remove"] = lambda registry, removed: self._finished() if removed == manager_id else None
            # First roundtrip creates handles, second receives COSMIC extension properties.
            roundtrip(self.display)
            roundtrip(self.display)
        except Exception:
            self.display.disconnect()
            raise

    def _properties(self, handle):
        # pywayland 0.4.19 associates incoming new_id proxies with the first
        # registry's Display. Idle and toplevels use separate connections;
        # transfer ownership before disconnect can destroy a foreign proxy.
        previous_display = handle._display
        if previous_display is not self.display:
            previous_display._children.discard(handle)
            handle._display = self.display
            self.display._children.add(handle)
        self.tracker.add(handle)
        handle.dispatcher["title"] = lambda proxy, title: self.tracker.update(handle, title=title)
        handle.dispatcher["app_id"] = lambda proxy, app_id: self.tracker.update(handle, app_id=app_id)
        handle.dispatcher["closed"] = lambda proxy: self._closed(handle)

    def _wlr_toplevel(self, manager, handle):
        self._properties(handle)
        handle.dispatcher["state"] = lambda proxy, states: self.tracker.update(handle, states=states)
        handle.dispatcher["done"] = lambda proxy: self.tracker.commit(handle)

    def _cosmic_toplevel(self, manager, handle):
        self._properties(handle)
        extension = self.info.get_cosmic_toplevel(handle)
        self._extensions[handle] = extension
        extension.dispatcher["state"] = lambda proxy, states: self.tracker.update(handle, states=states)
        # Metadata and activation arrive in distinct transactions.
        handle.dispatcher["done"] = lambda proxy: self.tracker.commit_metadata(handle)

    def _closed(self, handle):
        self.tracker.close(handle)
        extension = self._extensions.pop(handle, None)
        if extension:
            extension.destroy()
        handle.destroy()

    def _finished(self, *args):
        self.alive = False

    def dispatch(self):
        self.display.dispatch(block=False)
        self.display.flush()
        readable, _, _ = select.select([self.display.get_fd()], [], [], 0.2)
        if readable:
            self.display.dispatch(block=True)
        if not self.alive:
            raise RuntimeError("Compositor stopped publishing toplevels")

    def close(self):
        self.display.disconnect()


class WaylandActiveWindowBackend:
    def __init__(self):
        # Probe capabilities before selecting this backend; no display threads yet.
        self._client = WaylandToplevelClient()
        self._stop = threading.Event()
        self._thread = None
        self._fullscreen = None
        self.extension_notice = None

    def start_fullscreen_monitor(self, callback):
        self._fullscreen = callback

    def start(self, on_window_changed):
        previous = None

        def emit(app, title, fullscreen):
            nonlocal previous
            snapshot = (app, title, fullscreen)
            if self._stop.is_set() or previous == snapshot:
                return
            ts = int(time.time() * 1000)
            on_window_changed(app, title, ts)
            if self._fullscreen:
                self._fullscreen(fullscreen, ts)
            previous = snapshot

        def loop():
            while not self._stop.is_set():
                try:
                    if self._client is None:
                        self._client = WaylandToplevelClient()
                    self._client.tracker.callback = emit
                    self._client.tracker.publish()
                    self.extension_notice = None
                    while not self._stop.is_set():
                        self._client.dispatch()
                except Exception:
                    log.warning("Wayland toplevel connection lost; foreground paused")
                    self.extension_notice = "Связь с Wayland потеряна; учёт приложений приостановлен."
                    emit("", None, False)
                finally:
                    if self._client:
                        self._client.close()
                        self._client = None
                if self._stop.wait(1):
                    break

        self._thread = threading.Thread(target=loop, daemon=True, name="timetrace-wayland")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)
        elif self._client:
            self._client.close()
            self._client = None
