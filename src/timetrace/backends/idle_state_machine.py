# src/timetrace/backends/idle_state_machine.py
from typing import Literal

Transition = Literal["idled", "resumed", "none"]


class IdleStateMachine:
    def __init__(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms
        self._is_idle = False

    def update_threshold(self, threshold_ms: int) -> None:
        self._threshold_ms = threshold_ms

    def feed(self, idle_ms: int, now_ts: int) -> Transition:
        should_be_idle = idle_ms >= self._threshold_ms
        if should_be_idle and not self._is_idle:
            self._is_idle = True
            return "idled"
        if not should_be_idle and self._is_idle:
            self._is_idle = False
            return "resumed"
        return "none"
