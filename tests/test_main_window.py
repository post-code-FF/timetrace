# tests/test_main_window.py
from datetime import date, datetime, timezone

from timetrace.db import Store, day_bounds_ts
from timetrace.ui.main_window import MainWindow

UTC = timezone.utc


def test_main_window_shows_todays_data_on_construction(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, _ = day_bounds_ts(date(2026, 9, 27), UTC)
    store.open_presence_interval("active", day_start + 1000)
    store.close_open_presence_interval(day_start + 61_000)
    store.open_app_interval("firefox", "Mozilla Firefox", day_start + 1000)
    store.close_open_app_interval(day_start + 61_000)

    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)

    assert window.presence_track._intervals != []
    assert window.app_track._intervals != []
    store.close()


def test_main_window_date_nav_changes_shown_day(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    day1_start, _ = day_bounds_ts(date(2026, 9, 26), UTC)
    store.open_presence_interval("active", day1_start + 1000)
    store.close_open_presence_interval(day1_start + 61_000)

    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)
    assert window.presence_track._intervals == []  # today has no data

    window._date_nav._on_previous()
    assert window.presence_track._intervals != []  # yesterday has data
    store.close()


def test_main_window_total_label_reflects_active_presence_time(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, _ = day_bounds_ts(date(2026, 9, 27), UTC)
    store.open_presence_interval("active", day_start)
    store.close_open_presence_interval(day_start + 3_600_000)  # 1 hour active

    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)

    assert "1:00" in window.app_list._total_label.text()
    store.close()


def test_tracks_render_span_trimmed_to_actual_data_not_full_day(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, _ = day_bounds_ts(date(2026, 9, 27), UTC)
    tracked_start = day_start + 8 * 3_600_000  # 08:00
    tracked_end = day_start + 9 * 3_600_000  # 09:00
    store.open_presence_interval("active", tracked_start)
    store.close_open_presence_interval(tracked_end)

    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)

    assert window.presence_track._day_start_ts == tracked_start
    assert window.presence_track._day_end_ts == tracked_end
    assert window.app_track._day_start_ts == tracked_start
    assert window.app_track._day_end_ts == tracked_end
    store.close()


def test_main_window_settings_button_emits_signal(qtbot, tmp_path):
    store = Store(tmp_path / "data.db")
    fixed_now = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)
    window = MainWindow(store, tz=UTC, now_provider=lambda: fixed_now)
    qtbot.addWidget(window)

    with qtbot.waitSignal(window.settingsRequested, timeout=1000):
        window._settings_button.click()
    store.close()
