from typing import Callable, Protocol


class IdleBackend(Protocol):
    def start(
        self,
        threshold_ms: int,
        on_idle: Callable[[int], None],
        on_resume: Callable[[int], None],
    ) -> None: ...

    def update_threshold(self, threshold_ms: int) -> None: ...

    def stop(self) -> None: ...


class NullIdleBackend:
    def start(self, threshold_ms, on_idle, on_resume) -> None:
        pass

    def update_threshold(self, threshold_ms: int) -> None:
        pass

    def stop(self) -> None:
        pass
