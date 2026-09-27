from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtWidgets import QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from timetrace.app_color import color_for_resource_class
from timetrace.db import AppInterval
from timetrace.icons import resolve_icon


@dataclass(frozen=True)
class AppSummary:
    resource_class: str
    total_ms: int
    percent: float


def format_duration(ms: int) -> str:
    total_minutes = ms // 60_000
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}:{minutes:02d}"


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
        self._total_label = QLabel("Всего: 0:00")

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

    def set_total_label_text(self, text: str) -> None:
        """Allows main_window.py to override with the presence-based total (Task 22)."""
        self._total_label.setText(text)
