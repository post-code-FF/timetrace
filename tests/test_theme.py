# tests/test_theme.py
from timetrace.theme import read_system_color_scheme, watch_system_color_scheme


def test_reads_light_scheme():
    assert read_system_color_scheme(reader=lambda: 0) == "light"


def test_reads_dark_scheme():
    assert read_system_color_scheme(reader=lambda: 1) == "dark"


def test_unknown_value_maps_to_unknown():
    assert read_system_color_scheme(reader=lambda: 2) == "unknown"


def test_reader_raising_maps_to_unknown():
    def broken_reader():
        raise RuntimeError("no portal available")

    assert read_system_color_scheme(reader=broken_reader) == "unknown"


def test_watch_forwards_changes_and_unsubscribe_stops_forwarding():
    handlers = []

    def fake_subscriber(handler):
        handlers.append(handler)
        return lambda: handlers.remove(handler)

    events = []
    unsubscribe = watch_system_color_scheme(
        on_change=lambda scheme: events.append(scheme), subscriber=fake_subscriber
    )
    assert len(handlers) == 1

    handlers[0](1)  # portal reports "dark"
    assert events == ["dark"]

    unsubscribe()
    assert handlers == []
