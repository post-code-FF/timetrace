from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from timetrace.app_color import color_for_resource_class
from timetrace.db import AppInterval
from timetrace.icons import resolve_icon

_HIGHLIGHT_COLOR = QColor(100, 150, 220, 90)


@dataclass(frozen=True)
class AppSummary:
    resource_class: str
    total_ms: int
    percent: float


def format_duration(ms: int) -> str:
    total_seconds = ms // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}:{minutes:02d}:{seconds:02d}"


def aggregate_app_durations(intervals: Sequence[AppInterval]) -> list[AppSummary]:
    totals: dict[str, int] = {}
    for interval in intervals:
        duration = (interval.end_ts or 0) - interval.start_ts
        totals[interval.resource_class] = totals.get(interval.resource_class, 0) + duration

    grand_total = sum(totals.values())
    summaries = [
        AppSummary(
            resource_class=rc,
            total_ms=total,
            percent=(total / grand_total * 100.0) if grand_total else 0.0,
        )
        for rc, total in totals.items()
    ]
    summaries.sort(key=lambda s: s.total_ms, reverse=True)
    return summaries


class AppListWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = QTableWidget(0, 3, self)
        self._table.setHorizontalHeaderLabels(["Приложение", "Доля", "Длительность"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._total_label = QLabel("Всего: 0:00:00")
        self._highlighted_resource_class: str | None = None

        layout = QVBoxLayout(self)
        layout.addWidget(self._table)
        layout.addWidget(self._total_label)

    def set_intervals(self, intervals: Sequence[AppInterval]) -> None:
        summaries = aggregate_app_durations(intervals)
        self._table.setRowCount(len(summaries))
        for row, summary in enumerate(summaries):
            icon = resolve_icon(summary.resource_class)
            name_item = QTableWidgetItem(icon, summary.resource_class)
            self._table.setItem(row, 0, name_item)
            self._table.setItem(row, 1, QTableWidgetItem(f"{summary.percent:.1f}%"))
            self._table.setItem(row, 2, QTableWidgetItem(format_duration(summary.total_ms)))

        total_ms = sum(s.total_ms for s in summaries)
        self._total_label.setText(f"Всего: {format_duration(total_ms)}")
        self._apply_highlight()

    def set_total_label_text(self, text: str) -> None:
        """Allows main_window.py to override with the presence-based total (Task 22)."""
        self._total_label.setText(text)

    def set_highlighted_resource_class(self, resource_class: str | None) -> None:
        self._highlighted_resource_class = resource_class
        self._apply_highlight()

    def _apply_highlight(self) -> None:
        for row in range(self._table.rowCount()):
            name_item = self._table.item(row, 0)
            is_match = (
                self._highlighted_resource_class is not None
                and name_item is not None
                and name_item.text() == self._highlighted_resource_class
            )
            brush = QBrush(_HIGHLIGHT_COLOR) if is_match else QBrush()
            for col in range(self._table.columnCount()):
                cell = self._table.item(row, col)
                if cell is not None:
                    cell.setBackground(brush)
