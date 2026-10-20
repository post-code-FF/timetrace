from datetime import timezone

from timetrace.ui.time_ruler import TimeRulerWidget, compute_ticks

UTC = timezone.utc
H = 3_600_000


def test_ticks_align_to_round_times_and_scale_with_width():
    start = 6 * H + 33 * 60_000  # 06:33
    end = 7 * H + 21 * 60_000  # 07:21
    ticks = compute_ticks(start, end, 960.0, UTC)
    labels = [label for _x, label in ticks]
    assert labels[0] == "06:35" or labels[0] == "06:40"
    assert all(label[-2:] in ("00", "05", "10", "15", "20", "25", "30", "35", "40", "45", "50", "55")
               for label in labels)
    xs = [x for x, _ in ticks]
    assert all(b - a >= 64 for a, b in zip(xs, xs[1:]))
    assert all(0 <= x <= 960 for x in xs)


def test_ticks_empty_for_empty_range():
    assert compute_ticks(10, 10, 500.0, UTC) == []


def test_full_day_uses_hour_steps():
    ticks = compute_ticks(0, 24 * H, 1000.0, UTC)
    assert ticks[0][1] == "00:00"
    assert len(ticks) < 30


def test_ruler_paints_without_error(qtbot):
    ruler = TimeRulerWidget(UTC)
    qtbot.addWidget(ruler)
    ruler.resize(800, 28)
    ruler.set_range(6 * H, 8 * H)
    ruler.set_current_time_ts(7 * H)
    ruler.grab()
