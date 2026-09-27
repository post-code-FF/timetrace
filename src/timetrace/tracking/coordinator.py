# src/timetrace/tracking/coordinator.py
import queue
import time
from typing import Callable

from timetrace.backends.idle_base import IdleBackend
from timetrace.backends.window_base import ActiveWindowBackend
from timetrace.db import Store


def _default_clock() -> int:
    return int(time.time() * 1000)


class TrackingCoordinator:
    def __init__(
        self,
        store: Store,
        idle_backend: IdleBackend,
        window_backend: ActiveWindowBackend,
        idle_threshold_ms: int,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._store = store
        self._idle_backend = idle_backend
        self._window_backend = window_backend
        self._threshold_ms = idle_threshold_ms
        self._clock = clock or _default_clock
        self._queue: queue.Queue = queue.Queue()

        self._presence_state: str | None = None
        self._current_window: tuple[str, str | None] | None = None
        self._open_app_resource_class: str | None = None

    def start(self) -> None:
        now_ts = self._clock()
        self._store.reconcile_open_intervals_on_startup(fallback_end_ts=now_ts)

        self._store.open_presence_interval("active", now_ts)
        self._presence_state = "active"

        self._idle_backend.start(
            self._threshold_ms,
            on_idle=lambda ts: self._queue.put(("idle", ts)),
            on_resume=lambda ts: self._queue.put(("resume", ts)),
        )
        self._window_backend.start(
            lambda rc, title, ts: self._queue.put(("window", rc, title, ts))
        )

    def update_idle_threshold(self, minutes: int) -> None:
        self._threshold_ms = minutes * 60_000
        self._idle_backend.update_threshold(self._threshold_ms)

    def process_pending_events(self) -> None:
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                return
            self._apply(event)

    def _apply(self, event: tuple) -> None:
        kind = event[0]
        if kind == "idle":
            self._on_idle(event[1])
        elif kind == "resume":
            self._on_resume(event[1])
        elif kind == "window":
            self._on_window_changed(event[1], event[2], event[3])

    def _on_idle(self, ts: int) -> None:
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(ts)
            self._open_app_resource_class = None
        self._store.close_open_presence_interval(ts)
        self._store.open_presence_interval("idle", ts)
        self._presence_state = "idle"

    def _on_resume(self, ts: int) -> None:
        self._store.close_open_presence_interval(ts)
        self._store.open_presence_interval("active", ts)
        self._presence_state = "active"
        if self._current_window is not None:
            resource_class, title = self._current_window
            self._store.open_app_interval(resource_class, title, ts)
            self._open_app_resource_class = resource_class

    def _on_window_changed(self, resource_class: str, title: str | None, ts: int) -> None:
        self._current_window = (resource_class, title)
        if self._presence_state != "active":
            return
        if self._open_app_resource_class == resource_class:
            return  # same app still focused, ignore title-only churn
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(ts)
        self._store.open_app_interval(resource_class, title, ts)
        self._open_app_resource_class = resource_class

    def stop(self) -> None:
        now_ts = self._clock()
        self._idle_backend.stop()
        self._window_backend.stop()
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(now_ts)
            self._open_app_resource_class = None
        self._store.close_open_presence_interval(now_ts)
        self._presence_state = None
