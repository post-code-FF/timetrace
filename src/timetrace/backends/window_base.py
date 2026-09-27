from typing import Callable, Protocol


class ActiveWindowBackend(Protocol):
    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None: ...
    def stop(self) -> None: ...


class NullActiveWindowBackend:
    def start(self, on_window_changed) -> None:
        pass

    def stop(self) -> None:
        pass
