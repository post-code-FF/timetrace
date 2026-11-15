from timetrace.backends import window_factory
from timetrace.backends.window_base import NullActiveWindowBackend
from timetrace.backends.window_factory import select_window_backend
from timetrace.backends.session_gnome import GnomeSessionBackend
from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend
from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend


def test_x11_session_any_desktop_uses_ewmh_backend(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(window_factory, "X11EwmhActiveWindowBackend", lambda: sentinel)
    for desktop in ("kde", "gnome", "other"):
        assert select_window_backend(desktop, "x11") is sentinel


def test_x11_construction_failure_falls_back_to_null_backend(monkeypatch):
    def raise_on_construct():
        raise Exception("no X11 display")

    monkeypatch.setattr(window_factory, "X11EwmhActiveWindowBackend", raise_on_construct)
    assert isinstance(select_window_backend("kde", "x11"), NullActiveWindowBackend)


def test_kde_wayland_uses_kwin_script_backend():
    assert isinstance(select_window_backend("kde", "wayland"), KWinScriptActiveWindowBackend)


def test_gnome_wayland_uses_shell_extension_backend():
    assert isinstance(select_window_backend("gnome", "wayland"), GnomeSessionBackend)


def test_other_desktop_on_wayland_uses_null_backend(monkeypatch):
    def unavailable():
        raise RuntimeError("not supported")
    monkeypatch.setattr(window_factory, "WaylandActiveWindowBackend", unavailable)
    monkeypatch.setattr(window_factory, "PollingWindowBackend", unavailable)
    monkeypatch.setattr(window_factory, "kwin_available", lambda: False)
    assert isinstance(select_window_backend("other", "wayland"), NullActiveWindowBackend)


def test_unknown_desktop_uses_protocol_capabilities(monkeypatch):
    sentinel = object()
    monkeypatch.setattr(window_factory, "WaylandActiveWindowBackend", lambda: sentinel)
    assert select_window_backend("other", "wayland") is sentinel


def test_lxqt_with_kwin_uses_running_compositor(monkeypatch):
    def unavailable():
        raise RuntimeError("not supported")
    monkeypatch.setattr(window_factory, "WaylandActiveWindowBackend", unavailable)
    monkeypatch.setattr(window_factory, "kwin_available", lambda: True)
    sentinel = object()
    monkeypatch.setattr(window_factory, "KWinScriptActiveWindowBackend", lambda: sentinel)
    assert select_window_backend("other", "wayland") is sentinel


def test_cinnamon_uses_built_in_bridge(qtbot):
    from timetrace.backends.session_cinnamon import CinnamonSessionBackend
    assert isinstance(select_window_backend("cinnamon", "wayland"), CinnamonSessionBackend)
