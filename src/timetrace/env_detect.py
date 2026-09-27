from collections.abc import Mapping
from typing import Literal

DesktopEnv = Literal["kde", "gnome", "other"]
SessionType = Literal["x11", "wayland", "unknown"]


def detect_desktop_environment(env: Mapping[str, str] | None = None) -> DesktopEnv:
    import os

    e = env if env is not None else os.environ
    value = e.get("XDG_CURRENT_DESKTOP", "").upper()
    if "KDE" in value:
        return "kde"
    if "GNOME" in value:
        return "gnome"
    return "other"


def detect_session_type(env: Mapping[str, str] | None = None) -> SessionType:
    import os

    e = env if env is not None else os.environ
    value = e.get("XDG_SESSION_TYPE", "").lower()
    if value == "wayland":
        return "wayland"
    if value == "x11":
        return "x11"
    if e.get("WAYLAND_DISPLAY"):
        return "wayland"
    if e.get("DISPLAY"):
        return "x11"
    return "unknown"
