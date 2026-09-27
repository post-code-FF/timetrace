import threading
import time
from typing import Callable, Protocol


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

        self._display = Display()
        self._display.connect()
        registry = self._display.get_registry()
        self._state: dict[str, object] = {}

        def handle_global(registry, id_, interface, version):
            if interface == "ext_idle_notifier_v1":
                self._state["notifier"] = registry.bind(id_, ExtIdleNotifierV1, version)
            elif interface == "wl_seat":
                from timetrace._wayland_protocols.wayland import WlSeat

                self._state["seat"] = registry.bind(id_, WlSeat, version)

        registry.dispatcher["global"] = handle_global
        self._display.roundtrip()

        self._notifier = self._state["notifier"]
        self._seat = self._state["seat"]
        self._stop_event = threading.Event()
        self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatch_thread.start()

    def _dispatch_loop(self) -> None:
        while not self._stop_event.is_set():
            self._display.dispatch(block=True)

    def get_notification(self, timeout_ms, on_idled, on_resumed):
        notification = self._notifier.get_idle_notification(timeout_ms, self._seat)
        notification.dispatcher["idled"] = lambda n: on_idled()
        notification.dispatcher["resumed"] = lambda n: on_resumed()
        return notification

    def destroy_notification(self, handle) -> None:
        handle.destroy()

    def stop(self) -> None:
        self._stop_event.set()
        self._display.disconnect()


class WaylandExtIdleNotifyBackend:
    def __init__(self, client: ExtIdleClient | None = None) -> None:
        self._client = client or PywaylandExtIdleClient()
        self._threshold_ms = 0
        self._on_idle: Callable[[int], None] | None = None
        self._on_resume: Callable[[int], None] | None = None
        self._handle: object | None = None

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
        if self._on_idle:
            self._on_idle(int(time.time() * 1000))

    def _handle_resumed(self) -> None:
        if self._on_resume:
            self._on_resume(int(time.time() * 1000))

    def update_threshold(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms
        if self._handle is not None:
            self._client.destroy_notification(self._handle)
        self._request_notification()

    def stop(self) -> None:
        if self._handle is not None:
            self._client.destroy_notification(self._handle)
            self._handle = None
