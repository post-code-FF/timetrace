import threading
import time
from typing import Callable

from timetrace.backends.idle_state_machine import IdleStateMachine


def _real_query_idle_ms() -> int:
    from Xlib import display
    from Xlib.ext import screensaver

    d = display.Display()
    root = d.screen().root
    info = screensaver.query_info(d, root)
    return info.idle


class X11ScreenSaverIdleBackend:
    def __init__(
        self,
        query_idle_ms: Callable[[], int] | None = None,
        poll_interval_s: float = 1.0,
    ) -> None:
        self._query_idle_ms = query_idle_ms or _real_query_idle_ms
        self._poll_interval_s = poll_interval_s
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state_machine: IdleStateMachine | None = None

    def start(
        self,
        threshold_ms: int,
        on_idle: Callable[[int], None],
        on_resume: Callable[[int], None],
    ) -> None:
        self._state_machine = IdleStateMachine(threshold_ms)
        self._stop_event.clear()

        def loop() -> None:
            while not self._stop_event.is_set():
                try:
                    idle_ms = self._query_idle_ms()
                except Exception:
                    self._stop_event.wait(self._poll_interval_s)
                    continue
                now_ts = int(time.time() * 1000)
                assert self._state_machine is not None
                transition = self._state_machine.feed(idle_ms, now_ts)
                if transition == "idled":
                    on_idle(now_ts)
                elif transition == "resumed":
                    on_resume(now_ts)
                self._stop_event.wait(self._poll_interval_s)

        self._thread = threading.Thread(target=loop, daemon=True)
        self._thread.start()

    def update_threshold(self, threshold_ms: int) -> None:
        if self._state_machine is not None:
            self._state_machine.update_threshold(threshold_ms)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
