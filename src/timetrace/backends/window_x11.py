import threading
import time
from typing import Callable, Protocol


class X11Client(Protocol):
    def get_active_window_info(self) -> tuple[str, str | None] | None: ...
    def wait_for_active_window_change(self, timeout_s: float) -> bool: ...
    def close(self) -> None: ...


class RealX11Client:
    """Real client using python-xlib EWMH (_NET_ACTIVE_WINDOW)."""

    def __init__(self) -> None:
        from Xlib import X, display

        self._display = display.Display()
        self._root = self._display.screen().root
        self._net_active_window = self._display.intern_atom("_NET_ACTIVE_WINDOW")
        self._net_wm_pid = self._display.intern_atom("_NET_WM_PID")
        self._wm_class_atom = self._display.intern_atom("WM_CLASS")
        self._net_wm_state = self._display.intern_atom("_NET_WM_STATE")
        self._fullscreen_atom = self._display.intern_atom("_NET_WM_STATE_FULLSCREEN")
        self._window_type = self._display.intern_atom("_NET_WM_WINDOW_TYPE")
        self._shell_types = {self._display.intern_atom("_NET_WM_WINDOW_TYPE_" + name)
                             for name in ("DESKTOP", "DOCK", "NOTIFICATION", "TOOLTIP")}
        self._fullscreen = False
        self._root.change_attributes(event_mask=X.PropertyChangeMask)
        # change_attributes only queues the request; without a round trip the
        # event mask never reaches the server and no change events ever arrive.
        self._display.sync()

    def wait_for_active_window_change(self, timeout_s: float) -> bool:
        import select

        fd = self._display.fileno()
        readable, _, _ = select.select([fd], [], [], timeout_s)
        if not readable:
            return False
        changed = False
        while self._display.pending_events():
            event = self._display.next_event()
            if getattr(event, "atom", None) == self._net_active_window:
                changed = True
        return changed

    def get_active_window_info(self) -> tuple[str, str | None] | None:
        self._fullscreen = False
        prop = self._root.get_full_property(self._net_active_window, 0)
        if not prop or not prop.value:
            return None
        window_id = prop.value[0]
        if not window_id:
            return None
        window = self._display.create_resource_object("window", window_id)
        state = window.get_full_property(self._net_wm_state, 0)
        window_type = window.get_full_property(self._window_type, 0)
        shell_surface = window_type is not None and bool(self._shell_types.intersection(window_type.value))
        self._fullscreen = bool(state is not None and self._fullscreen_atom in state.value and not shell_surface)
        wm_class = window.get_wm_class()
        resource_class = wm_class[1] if wm_class else "unknown"
        wm_name = window.get_wm_name()
        title = wm_name if isinstance(wm_name, str) else None
        return resource_class, title

    def get_active_window_fullscreen(self) -> bool:
        return self._fullscreen

    def close(self) -> None:
        self._display.close()


class X11EwmhActiveWindowBackend:
    def __init__(self, xlib_client: X11Client | None = None) -> None:
        self._client = xlib_client or RealX11Client()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start_fullscreen_monitor(self, callback: Callable[[bool, int], None]) -> None:
        self._on_fullscreen = callback

    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None:
        self._stop_event.clear()

        def loop() -> None:
            previous = (None, False)
            try:
                while not self._stop_event.is_set():
                    try:
                        info = self._client.get_active_window_info()
                        get_fullscreen = getattr(self._client, "get_active_window_fullscreen", lambda: False)
                        fullscreen = bool(info and get_fullscreen())
                        snapshot = (info, fullscreen)
                        if snapshot != previous:
                            ts = int(time.time() * 1000)
                            on_window_changed(info[0] if info else "", info[1] if info else None, ts)
                            if getattr(self, "_on_fullscreen", None):
                                self._on_fullscreen(fullscreen, ts)
                            previous = snapshot
                    except Exception:
                        pass
                    # Re-sample on timeout too: fullscreen can change without
                    # changing _NET_ACTIVE_WINDOW (YouTube's fullscreen button).
                    try:
                        self._client.wait_for_active_window_change(0.5)
                    except Exception:
                        self._stop_event.wait(0.5)
            finally:
                self._client.close()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
