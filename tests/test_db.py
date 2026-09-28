# tests/test_db.py
from datetime import date, timezone

from timetrace.db import Store, day_bounds_ts

UTC = timezone.utc


def test_day_bounds_ts_local_midnight_to_midnight():
    start, end = day_bounds_ts(date(2026, 9, 27), UTC)
    assert end - start == 24 * 3600 * 1000
    assert start == 1790467200000  # 2026-09-27T00:00:00Z in ms


def test_presence_interval_open_close_and_query(tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, day_end = day_bounds_ts(date(2026, 9, 27), UTC)
    t0 = day_start + 3600_000  # 01:00
    t1 = day_start + 7200_000  # 02:00

    store.open_presence_interval("active", t0)
    assert store.get_open_presence_interval().state == "active"
    store.close_open_presence_interval(t1)
    assert store.get_open_presence_interval() is None

    rows = store.presence_intervals_for_day(day_start, day_end, now_ts=t1)
    assert len(rows) == 1
    assert rows[0].state == "active"
    assert rows[0].start_ts == t0
    assert rows[0].end_ts == t1
    store.close()


def test_presence_interval_crossing_midnight_is_clipped_per_day(tmp_path):
    store = Store(tmp_path / "data.db")
    day1_start, day1_end = day_bounds_ts(date(2026, 9, 27), UTC)
    day2_start, day2_end = day_bounds_ts(date(2026, 9, 28), UTC)
    start_ts = day1_end - 600_000  # 23:50 on day 1
    end_ts = day2_start + 600_000  # 00:10 on day 2

    store.open_presence_interval("active", start_ts)
    store.close_open_presence_interval(end_ts)

    day1_rows = store.presence_intervals_for_day(day1_start, day1_end, now_ts=end_ts)
    day2_rows = store.presence_intervals_for_day(day2_start, day2_end, now_ts=end_ts)

    assert len(day1_rows) == 1
    assert day1_rows[0].start_ts == start_ts
    assert day1_rows[0].end_ts == day1_end  # clipped to midnight

    assert len(day2_rows) == 1
    assert day2_rows[0].start_ts == day2_start  # clipped to midnight
    assert day2_rows[0].end_ts == end_ts
    store.close()


def test_open_interval_is_clipped_to_now_for_todays_query(tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, day_end = day_bounds_ts(date(2026, 9, 27), UTC)
    t0 = day_start + 1000
    now = day_start + 5000
    store.open_presence_interval("active", t0)

    rows = store.presence_intervals_for_day(day_start, day_end, now_ts=now)
    assert len(rows) == 1
    assert rows[0].end_ts == now
    store.close()


def test_app_interval_open_close_and_query(tmp_path):
    store = Store(tmp_path / "data.db")
    day_start, day_end = day_bounds_ts(date(2026, 9, 27), UTC)
    t0 = day_start + 1000
    t1 = day_start + 2000

    store.open_app_interval("firefox", "Mozilla Firefox", t0)
    assert store.get_open_app_interval().resource_class == "firefox"
    store.close_open_app_interval(t1)
    assert store.get_open_app_interval() is None

    rows = store.app_intervals_for_day(day_start, day_end, now_ts=t1)
    assert len(rows) == 1
    assert rows[0].resource_class == "firefox"
    assert rows[0].window_title == "Mozilla Firefox"
    store.close()


def test_reconcile_open_intervals_on_startup_closes_stale_rows(tmp_path):
    db_path = tmp_path / "data.db"
    store = Store(db_path)
    store.open_presence_interval("active", 1000)
    store.open_app_interval("vscode", None, 1000)
    store.close()

    # simulate process restart against the same file
    reopened = Store(db_path)
    reopened.reconcile_open_intervals_on_startup(fallback_end_ts=5000)

    assert reopened.get_open_presence_interval() is None
    assert reopened.get_open_app_interval() is None
    day_start, day_end = day_bounds_ts(date(1970, 1, 1), UTC)
    day_end = 10_000_000  # wide enough window covering ts around epoch
    rows = reopened.presence_intervals_for_day(0, day_end, now_ts=5000)
    assert rows[0].end_ts == 5000
    reopened.close()


def test_creating_store_creates_missing_parent_directory(tmp_path):
    db_path = tmp_path / "nested" / "dir" / "data.db"
    store = Store(db_path)
    assert db_path.exists()
    store.close()


def test_sleep_state_allowed_on_a_database_created_before_it_existed(tmp_path):
    import sqlite3

    db_path = tmp_path / "data.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE presence_intervals (
            id INTEGER PRIMARY KEY,
            state TEXT NOT NULL CHECK(state IN ('active', 'idle')),
            start_ts INTEGER NOT NULL,
            end_ts INTEGER
        );
        """
    )
    conn.execute(
        "INSERT INTO presence_intervals (state, start_ts, end_ts) VALUES ('active', 1000, 2000)"
    )
    conn.commit()
    conn.close()

    store = Store(db_path)  # must migrate the old CHECK constraint on open
    store.open_presence_interval("sleep", 3000)  # must not raise

    rows = store.presence_intervals_for_day(0, 10_000, now_ts=3000)
    assert {r.state for r in rows} == {"active", "sleep"}
    store.close()
