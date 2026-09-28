from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent

from timetrace.ui.timeline_widget import Segment, TimelineTrackWidget, intervals_to_segments


def _mouse_move_event(x: float, y: float) -> QMouseEvent:
    return QMouseEvent(
        QEvent.Type.MouseMove,
        QPointF(x, y),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )


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


def test_tiny_interval_gets_minimum_clickable_width():
    segments = intervals_to_segments(
        [(500, 501, (0, 255, 0))], day_start_ts=0, day_end_ts=1000, track_width_px=100
    )
    assert len(segments) == 1
    assert segments[0].width == 4.0
    # centered on the original (sub-pixel) midpoint: x=50.0, width=0.1
    assert segments[0].x == 48.05


def test_segment_resource_class_defaults_to_none_for_three_tuples():
    segments = intervals_to_segments(
        [(0, 1000, (0, 255, 0))], day_start_ts=0, day_end_ts=1000, track_width_px=100
    )
    assert segments == [Segment(x=0.0, width=100.0, color=(0, 255, 0), resource_class=None)]


def test_segment_carries_resource_class_from_four_tuples():
    segments = intervals_to_segments(
        [(0, 500, (0, 255, 0), "firefox"), (500, 1000, (255, 0, 0), "code")],
        day_start_ts=0,
        day_end_ts=1000,
        track_width_px=100,
    )
    assert [s.resource_class for s in segments] == ["firefox", "code"]


def test_hovering_over_segment_emits_its_resource_class(qtbot):
    widget = TimelineTrackWidget()
    widget.resize(100, 28)
    qtbot.addWidget(widget)
    widget.set_intervals(
        [(0, 500, (0, 255, 0), "firefox"), (500, 1000, (255, 0, 0), "code")],
        day_start_ts=0,
        day_end_ts=1000,
    )

    received = []
    widget.segmentHovered.connect(received.append)

    widget.mouseMoveEvent(_mouse_move_event(10, 5))
    assert received == ["firefox"]

    widget.mouseMoveEvent(_mouse_move_event(90, 5))
    assert received == ["firefox", "code"]


def test_leaving_widget_emits_none(qtbot):
    widget = TimelineTrackWidget()
    widget.resize(100, 28)
    qtbot.addWidget(widget)
    widget.set_intervals([(0, 1000, (0, 255, 0), "firefox")], day_start_ts=0, day_end_ts=1000)
    widget.mouseMoveEvent(_mouse_move_event(10, 5))

    received = []
    widget.segmentHovered.connect(received.append)
    widget.leaveEvent(QEvent(QEvent.Type.Leave))
    assert received == [None]
