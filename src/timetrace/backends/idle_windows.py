import ctypes
import threading
import time
from typing import Callable, Protocol


class InputSource(Protocol):
    def last_input_tick(self) -> int: ...
    def current_tick(self) -> int: ...


class Win32InputSource:
    def last_input_tick(self) -> int:
        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
        info = LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(LASTINPUTINFO)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            raise OSError("GetLastInputInfo failed")
        return info.dwTime

    def current_tick(self) -> int:
        return ctypes.windll.kernel32.GetTickCount64() & 0xFFFFFFFF


class WindowsIdleBackend:
    def __init__(self, input_source: InputSource | None = None, poll_interval_s: float = 0.5) -> None:
        self._input = input_source or Win32InputSource()
        self._poll_interval_s = poll_interval_s
        self._threshold_ms = 0
        self._idle = False
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._on_idle: Callable[[int], None] | None = None
        self._on_resume: Callable[[int], None] | None = None

    def start(self, threshold_ms: int, on_idle: Callable[[int], None], on_resume: Callable[[int], None]) -> None:
        self._threshold_ms = threshold_ms
        self._on_idle = on_idle
        self._on_resume = on_resume
        self._stop_event.clear()
        self._poll_once()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self) -> None:
        while not self._stop_event.wait(self._poll_interval_s):
            try:
                self._poll_once()
            except Exception:
                pass

    def _poll_once(self) -> None:
        elapsed = (self._input.current_tick() - self._input.last_input_tick()) & 0xFFFFFFFF
        idle = elapsed >= self._threshold_ms
        if idle == self._idle:
            return
        self._idle = idle
        ts = int(time.time() * 1000)
        if idle and self._on_idle:
            self._on_idle(ts)
        elif not idle and self._on_resume:
            self._on_resume(ts)

    def update_threshold(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None