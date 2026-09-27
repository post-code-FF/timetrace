from timetrace.backends.window_base import NullActiveWindowBackend
from timetrace.backends.window_factory import select_window_backend
from timetrace.backends.window_gnome import GnomeShellExtensionBackend
from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend
from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend


def test_x11_session_any_supported_desktop_uses_ewmh_backend():
    assert isinstance(select_window_backend("kde", "x11"), X11EwmhActiveWindowBackend)
    assert isinstance(select_window_backend("gnome", "x11"), X11EwmhActiveWindowBackend)


def test_kde_wayland_uses_kwin_script_backend():
    assert isinstance(select_window_backend("kde", "wayland"), KWinScriptActiveWindowBackend)


def test_gnome_wayland_uses_shell_extension_backend():
    assert isinstance(select_window_backend("gnome", "wayland"), GnomeShellExtensionBackend)


def test_unsupported_desktop_uses_null_backend():
    assert isinstance(select_window_backend("other", "x11"), NullActiveWindowBackend)
    assert isinstance(select_window_backend("other", "wayland"), NullActiveWindowBackend)
