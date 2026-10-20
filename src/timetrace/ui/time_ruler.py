from datetime import datetime, tzinfo

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

RULER_HEIGHT_PX = 28
MIN_TICK_GAP_PX = 64.0
_STEPS_MIN = (1, 2, 5, 10, 15, 30, 60, 120, 180, 360, 720)


def compute_ticks(
    start_ts: int, end_ts: int, width_px: float, tz: tzinfo
) -> list[tuple[float, str]]:
    """Метки шкалы времени: (x в пикселях, "ЧЧ:ММ") с шагом, подобранным под ширину."""
    span_ms = end_ts - start_ts
    if span_ms <= 0 or width_px <= 0:
        return []
    step_min = _STEPS_MIN[-1]
    for candidate in _STEPS_MIN:
        if candidate * 60_000 / span_ms * width_px >= MIN_TICK_GAP_PX:
            step_min = candidate
            break
    step_ms = step_min * 60_000
    offset_ms = int(datetime.fromtimestamp(start_ts / 1000, tz).utcoffset().total_seconds() * 1000)
    first = -((-(start_ts + offset_ms)) // step_ms) * step_ms - offset_ms
    ticks = []
    ts = first
    while ts <= end_ts:
        x = (ts - start_ts) / span_ms * width_px
        label = datetime.fromtimestamp(ts / 1000, tz).strftime("%H:%M")
        ticks.append((x, label))
        ts += step_ms
    return ticks


class TimeRulerWidget(QWidget):
    def __init__(self, tz: tzinfo, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tz = tz
        self._start_ts = 0
        self._end_ts = 0
        self._current_time_ts: int | None = None
        self.setFixedHeight(RULER_HEIGHT_PX)

    def set_range(self, start_ts: int, end_ts: int) -> None:
        self._start_ts = start_ts
        self._end_ts = end_ts
        self.update()

    def set_current_time_ts(self, ts: int | None) -> None:
        self._current_time_ts = ts
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        text_color = self.palette().color(self.foregroundRole())
        tick_color = QColor(text_color)
        tick_color.setAlpha(140)
        width = self.width()
        height = self.height()
        for x, label in compute_ticks(self._start_ts, self._end_ts, float(width), self._tz):
            painter.setPen(QPen(tick_color, 1))
            painter.drawLine(int(x), height - 6, int(x), height)
            painter.setPen(text_color)
            # Подпись центрируется на метке, но не вылезает за края виджета.
            text_width = painter.fontMetrics().horizontalAdvance(label)
            left = min(max(int(x) - text_width // 2, 0), max(width - text_width, 0))
            painter.drawText(left, 0, text_width + 2, height - 8, Qt.AlignBottom, label)
        if self._current_time_ts is not None and self._end_ts > self._start_ts:
            x = (self._current_time_ts - self._start_ts) / (self._end_ts - self._start_ts) * width
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            painter.drawLine(int(x), height - 6, int(x), height)
        painter.end()
