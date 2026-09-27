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
        self._root.change_attributes(event_mask=X.PropertyChangeMask)

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
        prop = self._root.get_full_property(self._net_active_window, 0)
        if not prop or not prop.value:
            return None
        window_id = prop.value[0]
        if not window_id:
            return None
        window = self._display.create_resource_object("window", window_id)
        wm_class = window.get_wm_class()
        resource_class = wm_class[1] if wm_class else "unknown"
        wm_name = window.get_wm_name()
        title = wm_name if isinstance(wm_name, str) else None
        return resource_class, title

    def close(self) -> None:
        self._display.close()


class X11EwmhActiveWindowBackend:
    def __init__(self, xlib_client: X11Client | None = None) -> None:
        self._client = xlib_client or RealX11Client()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None:
        self._stop_event.clear()

        def loop() -> None:
            while not self._stop_event.is_set():
                changed = self._client.wait_for_active_window_change(0.5)
                if changed and not self._stop_event.is_set():
                    info = self._client.get_active_window_info()
                    if info is not None:
                        resource_class, title = info
                        on_window_changed(resource_class, title, int(time.time() * 1000))
            self._client.close()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
