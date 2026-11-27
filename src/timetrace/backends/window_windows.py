import ctypes
import threading
import time
from typing import Callable, Protocol


class WindowsWindowClient(Protocol):
    def get_active_window_info(self) -> tuple[str, str | None] | None: ...
    def get_active_window_fullscreen(self) -> bool: ...
    def close(self) -> None: ...


class Win32WindowClient:
    def __init__(self) -> None:
        self._user32 = ctypes.windll.user32
        self._kernel32 = ctypes.windll.kernel32
        self._fullscreen = False

    def get_active_window_info(self) -> tuple[str, str | None] | None:
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            self._fullscreen = False
            return None
        length = self._user32.GetWindowTextLengthW(hwnd)
        buffer = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buffer, length + 1)
        title = buffer.value or None
        pid = ctypes.c_ulong()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        resource_class = self._process_name(pid.value) or "unknown"
        self._fullscreen = self._is_fullscreen(hwnd)
        return resource_class, title

    def _process_name(self, pid: int) -> str | None:
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = self._kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return None
        try:
            buffer = ctypes.create_unicode_buffer(32768)
            size = ctypes.c_ulong(len(buffer))
            if self._kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return buffer.value.rsplit("\\", 1)[-1]
        finally:
            self._kernel32.CloseHandle(handle)
        return None

    def _is_fullscreen(self, hwnd) -> bool:
        class RECT(ctypes.Structure):
            _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                        ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
        rect = RECT()
        if not self._user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        monitor = self._user32.MonitorFromWindow(hwnd, 2)
        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_ulong), ("rcMonitor", RECT),
                        ("rcWork", RECT), ("dwFlags", ctypes.c_ulong)]
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not self._user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return False
        return (rect.left <= info.rcMonitor.left and rect.top <= info.rcMonitor.top
                and rect.right >= info.rcMonitor.right and rect.bottom >= info.rcMonitor.bottom)

    def get_active_window_fullscreen(self) -> bool:
        return self._fullscreen

    def close(self) -> None:
        pass


class WindowsActiveWindowBackend:
    def __init__(self, client: WindowsWindowClient | None = None, poll_interval_s: float = 0.5) -> None:
        self._client = client or Win32WindowClient()
        self._poll_interval_s = poll_interval_s
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._on_fullscreen: Callable[[bool, int], None] | None = None

    def start_fullscreen_monitor(self, callback: Callable[[bool, int], None]) -> None:
        self._on_fullscreen = callback

    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None:
        self._stop_event.clear()

        def loop() -> None:
            previous = None
            try:
                while not self._stop_event.is_set():
                    try:
                        info = self._client.get_active_window_info()
                        fullscreen = bool(info and self._client.get_active_window_fullscreen())
                        snapshot = (info, fullscreen)
                        if snapshot != previous:
                            ts = int(time.time() * 1000)
                            on_window_changed(info[0] if info else "", info[1] if info else None, ts)
                            if self._on_fullscreen:
                                self._on_fullscreen(fullscreen, ts)
                            previous = snapshot
                    except Exception:
                        pass
                    self._stop_event.wait(self._poll_interval_s)
            finally:
                self._client.close()

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None