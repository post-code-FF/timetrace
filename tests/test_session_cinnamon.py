import pytest

from timetrace.backends.session_cinnamon import CinnamonSessionBackend


def test_idle_fullscreen_lock_and_failure_gate_foreground(qtbot):
    backend = CinnamonSessionBackend()
    windows, presence = [], []
    backend._window = lambda app, title, ts: windows.append((app, title))
    backend.start_presence_monitor(1000, lambda idle, blocked, ts: presence.append((idle, blocked)))
    snapshot = dict(app_id="firefox", title="film", fullscreen=True, idle_ms=2000, locked=False)
    backend._accept(snapshot)
    assert windows[-1] == ("firefox", "film")
    assert presence[-1] == (False, False)
    backend._accept(dict(snapshot, fullscreen=False))
    assert presence[-1] == (True, False)
    backend._accept(dict(snapshot, locked=True))
    assert windows[-1] == ("", None)
    assert presence[-1] == (False, True)
    backend._unavailable()
    assert windows[-1] == ("", None)
    assert presence[-1] == (False, True)


@pytest.mark.parametrize("change", [{"idle_ms": -1}, {"idle_ms": "0"}, {"locked": 1}, {"app_id": None}])
def test_invalid_idle_or_snapshot_cannot_charge_active_time(qtbot, change):
    backend = CinnamonSessionBackend()
    data = dict(app_id="app", title="", fullscreen=False, idle_ms=0, locked=False)
    with pytest.raises(ValueError):
        backend._accept(dict(data, **change))
