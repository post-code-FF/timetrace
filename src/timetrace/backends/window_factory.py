import logging
import sys

from timetrace.backends.window_base import ActiveWindowBackend, NullActiveWindowBackend
if sys.platform != "win32":
    from timetrace.backends.session_gnome import GnomeSessionBackend
    from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend
    from timetrace.backends.window_x11 import X11EwmhActiveWindowBackend
    from timetrace.backends.window_wayland import WaylandActiveWindowBackend
    from timetrace.backends.window_ipc import PollingWindowBackend
    from timetrace.backends.session_cinnamon import CinnamonSessionBackend
from timetrace.env_detect import DesktopEnv, SessionType

log = logging.getLogger(__name__)


def kwin_available():
    from PySide6.QtDBus import QDBusConnection
    interface = QDBusConnection.sessionBus().interface()
    if interface is None:
        return False
    for name in ("org.kde.KWin", "org.ukui.KWin"):
        reply = interface.isServiceRegistered(name)
        if reply.isValid() and reply.value():
            return True
    return False


def select_window_backend(desktop: DesktopEnv, session: SessionType) -> ActiveWindowBackend:
    if sys.platform == "win32":
        from timetrace.backends.window_windows import WindowsActiveWindowBackend
        try:
            return WindowsActiveWindowBackend()
        except Exception:
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
            return GnomeSessionBackend()
        except Exception:
            return NullActiveWindowBackend()
    if session == "wayland" and desktop == "cinnamon":
        return CinnamonSessionBackend()
    if session == "wayland":
        try:
            return WaylandActiveWindowBackend()
        except Exception:
            log.debug("Foreign-toplevel capability probe failed", exc_info=True)
        # LXQt and other shells can run on KWin without identifying as KDE.
        if kwin_available():
            return KWinScriptActiveWindowBackend()
        try:
            return PollingWindowBackend()
        except Exception:
            log.debug("Compositor IPC capability probe failed", exc_info=True)
        backend = NullActiveWindowBackend()
        backend.extension_notice = (
            "Этот Wayland-композитор не предоставляет поддерживаемый API активного окна; "
            "учёт приложений недоступен. См. docs/compatibility.md в репозитории TimeTrace."
        )
        return backend
    return NullActiveWindowBackend()
