from timetrace.backends import window_factory
from timetrace.backends.window_base import NullActiveWindowBackend
from timetrace.backends.window_factory import select_window_backend
from timetrace.backends.window_gnome import GnomeShellExtensionBackend
from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend
from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend


def test_x11_session_any_desktop_uses_ewmh_backend():
    for desktop in ("kde", "gnome", "other"):
        assert isinstance(select_window_backend(desktop, "x11"), X11EwmhActiveWindowBackend)


def test_x11_construction_failure_falls_back_to_null_backend(monkeypatch):
    def raise_on_construct():
        raise Exception("no X11 display")

    monkeypatch.setattr(window_factory, "X11EwmhActiveWindowBackend", raise_on_construct)
    assert isinstance(select_window_backend("kde", "x11"), NullActiveWindowBackend)


def test_kde_wayland_uses_kwin_script_backend():
    assert isinstance(select_window_backend("kde", "wayland"), KWinScriptActiveWindowBackend)


def test_gnome_wayland_uses_shell_extension_backend():
    assert isinstance(select_window_backend("gnome", "wayland"), GnomeShellExtensionBackend)


def test_other_desktop_on_wayland_uses_null_backend():
    assert isinstance(select_window_backend("other", "wayland"), NullActiveWindowBackend)
