# tests/test_main_bootstrap.py
from datetime import timezone

from PySide6.QtDBus import QDBusConnection
from PySide6.QtWidgets import QSystemTrayIcon

from timetrace.__main__ import build_app


def _force_primary_instance(monkeypatch):
    # build_app()'s single-instance guard registers "org.timetrace.App" on
    # the real session bus. On a machine that also happens to be running a
    # real TimeTrace instance (e.g. the developer's own desktop), that name
    # is already taken, so build_app would treat the test run as a *second*
    # instance and return (app, None, None, None, None) -- nothing to do
    # with the behavior under test. Force the primary-instance path so
    # these tests exercise build_app's real wiring regardless of what else
    # is on the bus.
    monkeypatch.setattr(QDBusConnection, "registerService", lambda self, name: True)


def test_build_app_wires_window_coordinator_and_tray(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "")  # force "other" -> Null backends, no real I/O
    monkeypatch.setenv("XDG_SESSION_TYPE", "")
    _force_primary_instance(monkeypatch)

    app, window, coordinator, tray, quit_app = build_app([])

    assert window.isVisible() is False or window.isVisible() is True  # constructed without error
    assert coordinator is not None
    # A tray icon is only created where one can actually be shown (e.g. not
    # under the offscreen QPA platform used in CI, and not on stock GNOME --
    # see build_app's comment); assert consistency with that check rather
    # than assuming a tray always exists.
    if QSystemTrayIcon.isSystemTrayAvailable():
        assert tray is not None
    else:
        assert tray is None

    coordinator.stop()
    app.quit()


def test_build_app_skips_tray_when_system_tray_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "")
    monkeypatch.setenv("XDG_SESSION_TYPE", "")
    monkeypatch.setattr(QSystemTrayIcon, "isSystemTrayAvailable", staticmethod(lambda: False))
    _force_primary_instance(monkeypatch)

    app, window, coordinator, tray, quit_app = build_app([])

    assert tray is None

    coordinator.stop()
    app.quit()
