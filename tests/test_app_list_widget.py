from timetrace.app_list_widget import aggregate_app_durations, format_duration
from timetrace.db import AppInterval


def test_format_duration_hours_and_minutes():
    assert format_duration(0) == "0:00"
    assert format_duration(60_000) == "0:01"
    assert format_duration(3_600_000) == "1:00"
    assert format_duration(3_660_000) == "1:01"
    assert format_duration(7_265_000) == "2:01"


def test_aggregate_sums_by_resource_class():
    intervals = [
        AppInterval(id=1, resource_class="firefox", window_title=None, start_ts=0, end_ts=60_000),
        AppInterval(id=2, resource_class="code", window_title=None, start_ts=60_000, end_ts=120_000),
        AppInterval(id=3, resource_class="firefox", window_title=None, start_ts=120_000, end_ts=180_000),
    ]
    summaries = aggregate_app_durations(intervals)
    by_class = {s.resource_class: s for s in summaries}
    assert by_class["firefox"].total_ms == 120_000
    assert by_class["code"].total_ms == 60_000


def test_aggregate_sorts_descending_by_duration():
    intervals = [
        AppInterval(id=1, resource_class="short", window_title=None, start_ts=0, end_ts=10_000),
        AppInterval(id=2, resource_class="long", window_title=None, start_ts=0, end_ts=100_000),
    ]
    summaries = aggregate_app_durations(intervals)
    assert [s.resource_class for s in summaries] == ["long", "short"]


def test_aggregate_computes_percent_of_total():
    intervals = [
        AppInterval(id=1, resource_class="a", window_title=None, start_ts=0, end_ts=75_000),
        AppInterval(id=2, resource_class="b", window_title=None, start_ts=0, end_ts=25_000),
    ]
    summaries = aggregate_app_durations(intervals)
    by_class = {s.resource_class: s for s in summaries}
    assert by_class["a"].percent == 75.0
    assert by_class["b"].percent == 25.0


def test_aggregate_empty_list():
    assert aggregate_app_durations([]) == []
