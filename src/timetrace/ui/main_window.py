# src/timetrace/ui/main_window.py
from datetime import datetime, tzinfo
from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from timetrace.app_names import display_name
from timetrace.app_color import color_for_resource_class
from timetrace.app_list_widget import AppListWidget, format_duration
from timetrace.db import Store, day_bounds_ts
from timetrace.ui.date_nav import DateNavBar
from timetrace.ui.time_ruler import TimeRulerWidget
from timetrace.ui.timeline_widget import TimelineTrackWidget

PRESENCE_COLORS = {"active": (46, 204, 64), "idle": (219, 68, 55), "sleep": (219, 68, 55)}
PRESENCE_LABELS = {"active": "Активен", "idle": "Простой", "sleep": "Спящий режим"}


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

        self.time_ruler = TimeRulerWidget(tz)
        self.presence_track = TimelineTrackWidget()
        self.app_track = TimelineTrackWidget()
        self.presence_track.set_timezone(tz)
        self.app_track.set_timezone(tz)
        tracks = QGridLayout()
        tracks.setHorizontalSpacing(8)
        tracks.setColumnStretch(1, 1)
        tracks.addWidget(self.time_ruler, 0, 1)
        tracks.addWidget(QLabel("Активность"), 1, 0)
        tracks.addWidget(self.presence_track, 1, 1)
        tracks.addWidget(QLabel("Приложения"), 2, 0)
        tracks.addWidget(self.app_track, 2, 1)
        layout.addLayout(tracks)

        self.app_list = AppListWidget()
        layout.addWidget(self.app_list)

        self.setCentralWidget(central)

        self.app_track.segmentHovered.connect(self.app_list.set_highlighted_resource_class)
        self.app_track.set_segment_label_resolver(lambda name: name)
        self.presence_track.set_segment_label_resolver(
            lambda state: PRESENCE_LABELS.get(state, state)
        )

        self._date_nav.dateChanged.connect(lambda _d: self.refresh())
        self.refresh()

    def refresh(self) -> None:
        selected_day = self._date_nav.selected_date()
        day_start_ts, day_end_ts = day_bounds_ts(selected_day, self._tz)
        now = self._now_provider()
        now_ts = int(now.timestamp() * 1000)

        presence_rows = self._store.presence_intervals_for_day(day_start_ts, day_end_ts, now_ts)
        presence_tuples = [
            (r.start_ts, r.end_ts, PRESENCE_COLORS.get(r.state, (128, 128, 128)), r.state)
            for r in presence_rows
        ]

        # Render only the span actually covered by tracked data (first event of
        # the day through the last), not the full midnight-to-midnight day --
        # otherwise most of the track is wasted gray for not-yet-lived time
        # today, or time before tracking started that day.
        if presence_rows:
            render_start_ts = min(r.start_ts for r in presence_rows)
            render_end_ts = max(r.end_ts for r in presence_rows)
        else:
            render_start_ts = render_end_ts = day_start_ts

        self.presence_track.set_intervals(presence_tuples, render_start_ts, render_end_ts)

        app_rows = self._store.app_intervals_for_day(day_start_ts, day_end_ts, now_ts)
        app_tuples = []
        for r in app_rows:
            name = display_name(r.resource_class, r.window_title)
            app_tuples.append((r.start_ts, r.end_ts, color_for_resource_class(name), name))
        self.app_track.set_intervals(app_tuples, render_start_ts, render_end_ts)
        self.time_ruler.set_range(render_start_ts, render_end_ts)

        is_today = selected_day == now.date()
        self.presence_track.set_current_time_ts(now_ts if is_today else None)
        self.app_track.set_current_time_ts(now_ts if is_today else None)
        self.time_ruler.set_current_time_ts(now_ts if is_today else None)

        self.app_list.set_intervals(app_rows)
        active_total_ms = sum(
            (r.end_ts or now_ts) - r.start_ts for r in presence_rows if r.state == "active"
        )
        self.app_list.set_total_label_text(f"Всего: {format_duration(active_total_ms)}")
