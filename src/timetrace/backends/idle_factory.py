import sys

from timetrace.backends.idle_base import IdleBackend, NullIdleBackend
if sys.platform != "win32":
    from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend
    from timetrace.backends.idle_x11 import X11ScreenSaverIdleBackend
from timetrace.env_detect import DesktopEnv, SessionType


def select_idle_backend(desktop: DesktopEnv, session: SessionType) -> IdleBackend:
    if sys.platform == "win32":
        from timetrace.backends.idle_windows import WindowsIdleBackend
        return WindowsIdleBackend()
    if session == "x11":
        return X11ScreenSaverIdleBackend()
    if session == "wayland" and desktop in ("gnome", "cinnamon"):
        return NullIdleBackend()  # The shell bridge supplies idle and lock together.
    if session == "wayland":
        try:
            return WaylandExtIdleNotifyBackend()
        except Exception:
            backend = NullIdleBackend()
            backend.extension_notice = "Этот композитор не предоставляет ext/KDE idle API; определение простоя недоступно."
            return backend
    return NullIdleBackend()
