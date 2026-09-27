# src/timetrace/db.py
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, tzinfo
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS presence_intervals (
    id INTEGER PRIMARY KEY,
    state TEXT NOT NULL CHECK(state IN ('active', 'idle')),
    start_ts INTEGER NOT NULL,
    end_ts INTEGER
);

CREATE TABLE IF NOT EXISTS app_intervals (
    id INTEGER PRIMARY KEY,
    resource_class TEXT NOT NULL,
    window_title TEXT,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER
);
"""


@dataclass(frozen=True)
class PresenceInterval:
    id: int
    state: str
    start_ts: int
    end_ts: int | None


@dataclass(frozen=True)
class AppInterval:
    id: int
    resource_class: str
    window_title: str | None
    start_ts: int
    end_ts: int | None


def day_bounds_ts(day: date, tz: tzinfo) -> tuple[int, int]:
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    start_ts = int(start.timestamp() * 1000)
    end_ts = int(end.timestamp() * 1000)
    return start_ts, end_ts


class Store:
    def __init__(self, db_path: str | Path) -> None:
        db_path = Path(db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def open_presence_interval(self, state: str, start_ts: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO presence_intervals (state, start_ts, end_ts) VALUES (?, ?, NULL)",
            (state, start_ts),
        )
        self._conn.commit()
        return cur.lastrowid

    def close_open_presence_interval(self, end_ts: int) -> None:
        self._conn.execute(
            "UPDATE presence_intervals SET end_ts = ? WHERE end_ts IS NULL", (end_ts,)
        )
        self._conn.commit()

    def get_open_presence_interval(self) -> PresenceInterval | None:
        row = self._conn.execute(
            "SELECT id, state, start_ts, end_ts FROM presence_intervals WHERE end_ts IS NULL"
        ).fetchone()
        return PresenceInterval(*row) if row else None

    def open_app_interval(self, resource_class: str, window_title: str | None, start_ts: int) -> int:
        cur = self._conn.execute(
            "INSERT INTO app_intervals (resource_class, window_title, start_ts, end_ts) "
            "VALUES (?, ?, ?, NULL)",
            (resource_class, window_title, start_ts),
        )
        self._conn.commit()
        return cur.lastrowid

    def close_open_app_interval(self, end_ts: int) -> None:
        self._conn.execute(
            "UPDATE app_intervals SET end_ts = ? WHERE end_ts IS NULL", (end_ts,)
        )
        self._conn.commit()

    def get_open_app_interval(self) -> AppInterval | None:
        row = self._conn.execute(
            "SELECT id, resource_class, window_title, start_ts, end_ts "
            "FROM app_intervals WHERE end_ts IS NULL"
        ).fetchone()
        return AppInterval(*row) if row else None

    def presence_intervals_for_day(
        self, day_start_ts: int, day_end_ts: int, now_ts: int
    ) -> list[PresenceInterval]:
        rows = self._conn.execute(
            "SELECT id, state, start_ts, end_ts FROM presence_intervals "
            "WHERE start_ts < ? AND (end_ts IS NULL OR end_ts > ?)",
            (day_end_ts, day_start_ts),
        ).fetchall()
        return [
            PresenceInterval(
                id=r[0],
                state=r[1],
                start_ts=max(r[2], day_start_ts),
                end_ts=min(r[3] if r[3] is not None else now_ts, day_end_ts),
            )
            for r in rows
        ]

    def app_intervals_for_day(
        self, day_start_ts: int, day_end_ts: int, now_ts: int
    ) -> list[AppInterval]:
        rows = self._conn.execute(
            "SELECT id, resource_class, window_title, start_ts, end_ts FROM app_intervals "
            "WHERE start_ts < ? AND (end_ts IS NULL OR end_ts > ?)",
            (day_end_ts, day_start_ts),
        ).fetchall()
        return [
            AppInterval(
                id=r[0],
                resource_class=r[1],
                window_title=r[2],
                start_ts=max(r[3], day_start_ts),
                end_ts=min(r[4] if r[4] is not None else now_ts, day_end_ts),
            )
            for r in rows
        ]

    def reconcile_open_intervals_on_startup(self, fallback_end_ts: int) -> None:
        self.close_open_presence_interval(fallback_end_ts)
        self.close_open_app_interval(fallback_end_ts)
