# src/timetrace/tracking/coordinator.py
import queue
import sys
import time
from typing import Callable

from timetrace.backends.idle_base import IdleBackend, NullIdleBackend
from timetrace.backends.sleep_monitor import NullSleepMonitor, SleepBackend
from timetrace.backends.window_base import ActiveWindowBackend, NullActiveWindowBackend
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
        sleep_backend: SleepBackend | None = None,
    ) -> None:
        self._store = store
        self._idle_backend = idle_backend
        self._window_backend = window_backend
        self._sleep_backend = sleep_backend or NullSleepMonitor()
        self._threshold_ms = idle_threshold_ms
        self._clock = clock or _default_clock
        self._queue: queue.Queue = queue.Queue()

        self._idle = False
        self._sleeping = False
        self._blocked = False
        self._stopped = False
        self._last_ts = 0
        self._presence_state: str | None = None
        self._current_window: tuple[str, str | None] | None = None
        self._open_app_resource_class: str | None = None

    def start(self) -> None:
        now_ts = self._clock()
        self._last_ts = now_ts
        self._blocked = hasattr(self._window_backend, "start_presence_monitor")
        self._store.reconcile_open_intervals_on_startup(fallback_end_ts=now_ts)

        self._presence_state = "idle" if self._blocked else "active"
        self._store.open_presence_interval(self._presence_state, now_ts)
        if hasattr(self._window_backend, "start_presence_monitor"):
            self._window_backend.start_presence_monitor(
                self._threshold_ms,
                lambda idle, blocked, ts: self._queue.put(("session", idle, blocked, ts)),
            )

        # A real backend's start() touches live D-Bus services, subprocesses, or
        # window-system connections whose exact behavior varies across desktop
        # environment versions in ways construction-time checks can't catch.
        # Never let that take down the whole app before the window can even
        # appear -- degrade to a Null backend and keep going.
        try:
            self._idle_backend.start(
                self._threshold_ms,
                on_idle=lambda ts: self._queue.put(("idle", ts)),
                on_resume=lambda ts: self._queue.put(("resume", ts)),
            )
        except Exception as exc:
            print(f"timetrace: idle backend failed to start, disabling it: {exc}", file=sys.stderr)
            self._idle_backend = NullIdleBackend()

        try:
            self._window_backend.start(
                lambda rc, title, ts: self._queue.put(("window", rc, title, ts))
            )
        except Exception as exc:
            print(f"timetrace: window backend failed to start, disabling it: {exc}", file=sys.stderr)
            self._window_backend = NullActiveWindowBackend()

        try:
            self._sleep_backend.start(
                on_sleep=lambda ts: self._queue.put(("sleep", ts)),
                on_wake=lambda ts: self._queue.put(("wake", ts)),
            )
        except Exception as exc:
            print(f"timetrace: sleep monitor failed to start, disabling it: {exc}", file=sys.stderr)
            self._sleep_backend = NullSleepMonitor()

    def update_idle_threshold(self, minutes: int) -> None:
        self._threshold_ms = minutes * 60_000
        self._idle_backend.update_threshold(self._threshold_ms)
        if hasattr(self._window_backend, "update_threshold"):
            self._window_backend.update_threshold(self._threshold_ms)

    def process_pending_events(self) -> None:
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                return
            ts = max(self._last_ts, event[-1])
            event = (*event[:-1], ts)
            with self._store.transaction():
                self._apply(event)
                self._store.checkpoint(ts)
            self._last_ts = ts

    def _apply(self, event: tuple) -> None:
        kind = event[0]
        if kind == "idle":
            self._on_idle(event[1])
        elif kind == "resume":
            self._on_resume(event[1])
        elif kind == "sleep":
            self._on_sleep(event[1])
        elif kind == "wake":
            self._sleeping = False
            self._refresh_presence(event[1])
        elif kind == "session":
            self._idle, self._blocked = event[1], event[2]
            self._refresh_presence(event[3])
        elif kind == "window":
            self._on_window_changed(event[1], event[2], event[3])

    def _on_idle(self, ts: int) -> None:
        self._idle = True
        self._refresh_presence(ts)

    def _on_sleep(self, ts: int) -> None:
        self._sleeping = True
        self._refresh_presence(ts)

    def _on_resume(self, ts: int) -> None:
        self._idle = False
        self._refresh_presence(ts)

    def _refresh_presence(self, ts: int) -> None:
        state = "sleep" if self._sleeping else ("idle" if self._idle or self._blocked else "active")
        if state == self._presence_state:
            return
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(ts)
            self._open_app_resource_class = None
        self._store.close_open_presence_interval(ts)
        self._store.open_presence_interval(state, ts)
        self._presence_state = state
        if state == "active" and self._current_window is not None:
            resource_class, title = self._current_window
            self._store.open_app_interval(resource_class, title, ts)
            self._open_app_resource_class = resource_class

    def _on_window_changed(self, resource_class: str, title: str | None, ts: int) -> None:
        self._current_window = (resource_class, title) if resource_class else None
        if self._presence_state != "active":
            return
        if self._open_app_resource_class == resource_class:
            return  # same app still focused, ignore title-only churn
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(ts)
        self._open_app_resource_class = None
        if resource_class:
            self._store.open_app_interval(resource_class, title, ts)
            self._open_app_resource_class = resource_class

    def checkpoint(self) -> None:
        self.process_pending_events()
        self._store.checkpoint(max(self._last_ts, self._clock()))

    def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        self.process_pending_events()
        now_ts = max(self._last_ts, self._clock())
        for backend in (self._idle_backend, self._window_backend, self._sleep_backend):
            try:
                backend.stop()
            except Exception as exc:
                print(f"timetrace: backend cleanup failed: {exc}", file=sys.stderr)
        if self._open_app_resource_class is not None:
            self._store.close_open_app_interval(now_ts)
            self._open_app_resource_class = None
        self._store.close_open_presence_interval(now_ts)
        self._presence_state = None
