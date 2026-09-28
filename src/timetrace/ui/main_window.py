# src/timetrace/ui/main_window.py
from datetime import datetime, tzinfo
from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QToolButton, QVBoxLayout, QWidget

from timetrace.app_color import color_for_resource_class
from timetrace.app_list_widget import AppListWidget, format_duration
from timetrace.db import Store, day_bounds_ts
from timetrace.ui.date_nav import DateNavBar
from timetrace.ui.timeline_widget import TimelineTrackWidget

PRESENCE_COLORS = {"active": (46, 204, 64), "idle": (219, 68, 55)}


class MainWindow(QMainWindow):
    settingsRequested = Signal()

    def __init__(
        self,
        store: Store,
        tz: tzinfo,
        now_provider: Callable[[], datetime] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._tz = tz
        self._now_provider = now_provider or (lambda: datetime.now(tz))

        self.setWindowTitle("TimeTrace")
        self.setMinimumSize(760, 620)
        self.resize(1000, 820)

        central = QWidget(self)
        layout = QVBoxLayout(central)

        top_row = QHBoxLayout()
        self._date_nav = DateNavBar(self._now_provider().date())
        self._settings_button = QToolButton()
        self._settings_button.setText("⚙")
        self._settings_button.clicked.connect(self.settingsRequested.emit)
        top_row.addWidget(self._date_nav)
        top_row.addStretch()
        top_row.addWidget(self._settings_button)
        layout.addLayout(top_row)

        self.presence_track = TimelineTrackWidget()
        self.app_track = TimelineTrackWidget()
        layout.addWidget(self.presence_track)
        layout.addWidget(self.app_track)

        self.app_list = AppListWidget()
        layout.addWidget(self.app_list)

        self.setCentralWidget(central)

        self.app_track.segmentHovered.connect(self.app_list.set_highlighted_resource_class)

        self._date_nav.dateChanged.connect(lambda _d: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        selected_day = self._date_nav.selected_date()
        day_start_ts, day_end_ts = day_bounds_ts(selected_day, self._tz)
        now = self._now_provider()
        now_ts = int(now.timestamp() * 1000)

        presence_rows = self._store.presence_intervals_for_day(day_start_ts, day_end_ts, now_ts)
        presence_tuples = [
            (r.start_ts, r.end_ts, PRESENCE_COLORS.get(r.state, (128, 128, 128)))
            for r in presence_rows
        ]
        self.presence_track.set_intervals(presence_tuples, day_start_ts, day_end_ts)

        app_rows = self._store.app_intervals_for_day(day_start_ts, day_end_ts, now_ts)
        app_tuples = [
            (r.start_ts, r.end_ts, color_for_resource_class(r.resource_class), r.resource_class)
            for r in app_rows
        ]
        self.app_track.set_intervals(app_tuples, day_start_ts, day_end_ts)

        is_today = selected_day == now.date()
        self.presence_track.set_current_time_ts(now_ts if is_today else None)
        self.app_track.set_current_time_ts(now_ts if is_today else None)

        self.app_list.set_intervals(app_rows)
        active_total_ms = sum(
            (r.end_ts or now_ts) - r.start_ts for r in presence_rows if r.state == "active"
        )
        self.app_list.set_total_label_text(f"Всего: {format_duration(active_total_ms)}")
