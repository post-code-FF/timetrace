from timetrace.backends.idle_base import IdleBackend, NullIdleBackend
from timetrace.backends.idle_gnome import MutterIdleMonitorBackend
from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend
from timetrace.backends.idle_x11 import X11ScreenSaverIdleBackend
from timetrace.env_detect import DesktopEnv, SessionType


def select_idle_backend(desktop: DesktopEnv, session: SessionType) -> IdleBackend:
    if desktop not in ("kde", "gnome"):
        return NullIdleBackend()
    if session == "x11":
        return X11ScreenSaverIdleBackend()
    if session == "wayland" and desktop == "gnome":
        try:
            return MutterIdleMonitorBackend()
        except Exception:
            return NullIdleBackend()
    if session == "wayland" and desktop == "kde":
        try:
            return WaylandExtIdleNotifyBackend()
        except Exception:
            return NullIdleBackend()
    return NullIdleBackend()
