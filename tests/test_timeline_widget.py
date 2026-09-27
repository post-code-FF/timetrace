from timetrace.ui.timeline_widget import Segment, intervals_to_segments


def test_empty_intervals_produce_no_segments():
    assert intervals_to_segments([], day_start_ts=0, day_end_ts=1000, track_width_px=100) == []


def test_full_day_interval_spans_full_width():
    segments = intervals_to_segments(
        [(0, 1000, (0, 255, 0))], day_start_ts=0, day_end_ts=1000, track_width_px=100
    )
    assert segments == [Segment(x=0.0, width=100.0, color=(0, 255, 0))]


def test_half_day_interval_spans_half_width():
    segments = intervals_to_segments(
        [(0, 500, (0, 255, 0))], day_start_ts=0, day_end_ts=1000, track_width_px=100
    )
    assert segments == [Segment(x=0.0, width=50.0, color=(0, 255, 0))]


def test_interval_offset_from_day_start():
    segments = intervals_to_segments(
        [(250, 750, (255, 0, 0))], day_start_ts=0, day_end_ts=1000, track_width_px=100
    )
    assert segments == [Segment(x=25.0, width=50.0, color=(255, 0, 0))]


def test_multiple_intervals_preserve_order():
    segments = intervals_to_segments(
        [(0, 250, (0, 255, 0)), (250, 1000, (255, 0, 0))],
        day_start_ts=0,
        day_end_ts=1000,
        track_width_px=100,
    )
    assert [s.color for s in segments] == [(0, 255, 0), (255, 0, 0)]
    assert segments[1].x == 25.0
    assert segments[1].width == 75.0
