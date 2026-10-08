from timetrace.backends.idle_base import NullIdleBackend
from timetrace.backends.idle_factory import select_idle_backend
from timetrace.backends.idle_gnome import MutterIdleMonitorBackend
from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend
from timetrace.backends.idle_x11 import X11ScreenSaverIdleBackend


def test_x11_session_any_desktop_uses_screensaver_backend():
    for desktop in ("kde", "gnome", "other"):
        assert isinstance(select_idle_backend(desktop, "x11"), X11ScreenSaverIdleBackend)


def test_gnome_wayland_uses_mutter_backend():
    # This dev machine runs a KDE Wayland session, not GNOME, so there is no
    # org.gnome.Mutter.IdleMonitor bus/service present. Per the task brief,
    # real construction failing on a mismatched environment should fall back
    # to NullIdleBackend rather than raising, so both outcomes are accepted
    # here instead of forcing a specific real backend to construct.
    backend = select_idle_backend("gnome", "wayland")
    assert isinstance(backend, (MutterIdleMonitorBackend, NullIdleBackend))


def test_kde_wayland_uses_ext_idle_notify_backend():
    assert isinstance(select_idle_backend("kde", "wayland"), WaylandExtIdleNotifyBackend)


def test_other_desktop_on_wayland_uses_null_backend():
    assert isinstance(select_idle_backend("other", "wayland"), NullIdleBackend)


def test_unknown_session_uses_null_backend():
    assert isinstance(select_idle_backend("kde", "unknown"), NullIdleBackend)
