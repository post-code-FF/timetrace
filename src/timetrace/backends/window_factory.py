from timetrace.backends.window_base import ActiveWindowBackend, NullActiveWindowBackend
from timetrace.backends.window_gnome import GnomeShellExtensionBackend
from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend
from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend
from timetrace.env_detect import DesktopEnv, SessionType


def select_window_backend(desktop: DesktopEnv, session: SessionType) -> ActiveWindowBackend:
    if desktop not in ("kde", "gnome"):
        return NullActiveWindowBackend()
    if session == "x11":
        try:
            return X11EwmhActiveWindowBackend()
        except Exception:
            return NullActiveWindowBackend()
    if session == "wayland" and desktop == "kde":
        try:
            return KWinScriptActiveWindowBackend()
        except Exception:
            return NullActiveWindowBackend()
    if session == "wayland" and desktop == "gnome":
        try:
            return GnomeShellExtensionBackend()
        except Exception:
            return NullActiveWindowBackend()
    return NullActiveWindowBackend()
