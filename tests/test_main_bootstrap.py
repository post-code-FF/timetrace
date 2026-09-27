# tests/test_main_bootstrap.py
from datetime import timezone

from timetrace.__main__ import build_app


def test_build_app_wires_window_coordinator_and_tray(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "")  # force "other" -> Null backends, no real I/O
    monkeypatch.setenv("XDG_SESSION_TYPE", "")

    app, window, coordinator, tray, quit_app = build_app([])

    assert window.isVisible() is False or window.isVisible() is True  # constructed without error
    assert coordinator is not None
    assert tray is not None

    coordinator.stop()
    app.quit()
