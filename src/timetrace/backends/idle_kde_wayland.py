import select
import threading
import time
from typing import Callable, Protocol

from timetrace.backends.wayland_connection import roundtrip


class ExtIdleClient(Protocol):
    def get_notification(
        self, timeout_ms: int, on_idled: Callable[[], None], on_resumed: Callable[[], None]
    ) -> object: ...
    def destroy_notification(self, handle: object) -> None: ...
    def stop(self) -> None: ...


class PywaylandExtIdleClient:
    """Real client using the bindings generated in Task 2."""

    def __init__(self) -> None:
        from pywayland.client import Display

        from timetrace._wayland_protocols.ext_idle_notify_v1 import ExtIdleNotifierV1
        from timetrace._wayland_protocols.kde_idle import OrgKdeKwinIdle

        self._display = Display()
        self._display.connect()
        registry = self._display.get_registry()
        self._state: dict[str, object] = {}
        self._notifier_version = 1

        def handle_global(registry, id_, interface, version):
            if interface == "ext_idle_notifier_v1":
                self._notifier_version = min(version, ExtIdleNotifierV1.version)
                self._state["notifier"] = registry.bind(id_, ExtIdleNotifierV1, self._notifier_version)
            elif interface == "wl_seat":
                from timetrace._wayland_protocols.wayland import WlSeat

                self._state["seat"] = registry.bind(id_, WlSeat, min(version, WlSeat.version))
            elif interface == "org_kde_kwin_idle":
                self._state["legacy_notifier"] = registry.bind(id_, OrgKdeKwinIdle, 1)

        registry.dispatcher["global"] = handle_global
        try:
            roundtrip(self._display)
        except Exception:
            self._display.disconnect()
            raise

        try:
            self._using_legacy = "notifier" not in self._state
            self._notifier = self._state["legacy_notifier" if self._using_legacy else "notifier"]
            self._seat = self._state["seat"]
        except KeyError:
            self._display.disconnect()
            raise RuntimeError("Compositor does not support ext/KDE idle notification or wl_seat")
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatch_thread.start()

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                self._display.dispatch(block=False)
                self._display.flush()
            readable, _, _ = select.select([self._display.get_fd()], [], [], 0.2)
            if readable and not self._stop_event.is_set():
                with self._lock:
                    self._display.dispatch(block=True)

    def get_notification(self, timeout_ms, on_idled, on_resumed):
        with self._lock:
            # v2 ignores idle inhibitors from unrelated/background surfaces.
            # Fullscreen exemptions are applied explicitly by the coordinator.
            if self._using_legacy:
                notification = self._notifier.get_idle_timeout(self._seat, timeout_ms)
            else:
                request = (self._notifier.get_input_idle_notification if self._notifier_version >= 2
                           else self._notifier.get_idle_notification)
                notification = request(timeout_ms, self._seat)
            notification.dispatcher["idle" if self._using_legacy else "idled"] = lambda n: on_idled()
            notification.dispatcher["resumed"] = lambda n: on_resumed()
            self._display.flush()
        return notification

    def destroy_notification(self, handle) -> None:
        with self._lock:
            if self._using_legacy:
                handle.release()
            else:
                handle.destroy()
            self._display.flush()

    def stop(self) -> None:
        self._stop_event.set()
        self._dispatch_thread.join(timeout=2)
        self._display.disconnect()


class WaylandExtIdleNotifyBackend:
    def __init__(self, client: ExtIdleClient | None = None) -> None:
        self._client = client or PywaylandExtIdleClient()
        self._threshold_ms = 0
        self._on_idle: Callable[[int], None] | None = None
        self._on_resume: Callable[[int], None] | None = None
        self._handle: object | None = None
        self._idled = False

    def start(
        self,
        threshold_ms: int,
        on_idle: Callable[[int], None],
        on_resume: Callable[[int], None],
    ) -> None:
        self._threshold_ms = threshold_ms
        self._on_idle = on_idle
        self._on_resume = on_resume
        self._request_notification()

    def _request_notification(self) -> None:
        self._handle = self._client.get_notification(
            self._threshold_ms, self._handle_idled, self._handle_resumed
        )

    def _handle_idled(self) -> None:
        self._idled = True
        if self._on_idle:
            self._on_idle(int(time.time() * 1000))

    def _handle_resumed(self) -> None:
        self._idled = False
        if self._on_resume:
            self._on_resume(int(time.time() * 1000))

    def update_threshold(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms
        if self._handle is not None:
            self._client.destroy_notification(self._handle)
        if self._idled:
            self._handle_resumed()
        self._request_notification()

    def stop(self) -> None:
        if self._handle is not None:
            self._client.destroy_notification(self._handle)
            self._handle = None
        self._client.stop()
