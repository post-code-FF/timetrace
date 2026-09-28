from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QRectF, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QToolTip, QWidget

TRACK_HEIGHT_PX = 96
MIN_SEGMENT_WIDTH_PX = 4.0


@dataclass(frozen=True)
class Segment:
    x: float
    width: float
    color: tuple[int, int, int]
    resource_class: str | None = None


def intervals_to_segments(
    intervals: Sequence[tuple],
    day_start_ts: int,
    day_end_ts: int,
    track_width_px: float,
) -> list[Segment]:
    day_span = day_end_ts - day_start_ts
    if day_span <= 0:
        return []
    segments = []
    for interval in intervals:
        start_ts, end_ts, color = interval[0], interval[1], interval[2]
        resource_class = interval[3] if len(interval) > 3 else None
        x = (start_ts - day_start_ts) / day_span * track_width_px
        width = (end_ts - start_ts) / day_span * track_width_px
        if width < MIN_SEGMENT_WIDTH_PX:
            x -= (MIN_SEGMENT_WIDTH_PX - width) / 2
            width = MIN_SEGMENT_WIDTH_PX
        segments.append(Segment(x=x, width=width, color=color, resource_class=resource_class))
    return segments


def _brighten(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return tuple(min(255, c + int((255 - c) * 0.5)) for c in color)


class TimelineTrackWidget(QWidget):
    segmentHovered = Signal(object)  # str | None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(TRACK_HEIGHT_PX)
        self.setMouseTracking(True)
        self._intervals: list[tuple] = []
        self._day_start_ts = 0
        self._day_end_ts = 1
        self._current_time_ts: int | None = None
        self._hovered_resource_class: str | None = None
        self._segment_label_resolver: Callable[[str], str] | None = None

    def set_segment_label_resolver(self, resolver: Callable[[str], str] | None) -> None:
        """Opt-in tooltip: when set, hovering a segment shows resolver(resource_class)."""
        self._segment_label_resolver = resolver

    def set_intervals(
        self,
        intervals: Sequence[tuple],
        day_start_ts: int,
        day_end_ts: int,
    ) -> None:
        self._intervals = list(intervals)
        self._day_start_ts = day_start_ts
        self._day_end_ts = day_end_ts
        self.update()

    def set_current_time_ts(self, ts: int | None) -> None:
        self._current_time_ts = ts
        self.update()

    def mouseMoveEvent(self, event) -> None:
        segments = intervals_to_segments(
            self._intervals, self._day_start_ts, self._day_end_ts, float(self.width())
        )
        pos_x = event.position().x()
        hovered = None
        for segment in segments:
            if segment.x <= pos_x < segment.x + segment.width:
                hovered = segment.resource_class
                break
        self._set_hovered(hovered)

        if self._segment_label_resolver is not None:
            if hovered is not None:
                QToolTip.showText(
                    event.globalPosition().toPoint(), self._segment_label_resolver(hovered), self
                )
            else:
                QToolTip.hideText()

    def leaveEvent(self, event) -> None:
        self._set_hovered(None)
        if self._segment_label_resolver is not None:
            QToolTip.hideText()
        super().leaveEvent(event)

    def _set_hovered(self, resource_class: str | None) -> None:
        if resource_class != self._hovered_resource_class:
            self._hovered_resource_class = resource_class
            self.segmentHovered.emit(resource_class)
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        width = self.width()
        height = self.height()

        painter.fillRect(0, 0, width, height, QColor(60, 60, 60))

        segments = intervals_to_segments(
            self._intervals, self._day_start_ts, self._day_end_ts, float(width)
        )
        for segment in segments:
            color = segment.color
            if (
                self._hovered_resource_class is not None
                and segment.resource_class == self._hovered_resource_class
            ):
                color = _brighten(color)
            painter.fillRect(QRectF(segment.x, 0, segment.width, height), QColor(*color))

        if self._current_time_ts is not None:
            day_span = self._day_end_ts - self._day_start_ts
            if day_span > 0:
                x = (self._current_time_ts - self._day_start_ts) / day_span * width
                painter.setPen(QPen(QColor(255, 0, 0), 2))
                painter.drawLine(int(x), 0, int(x), height)

        painter.end()
