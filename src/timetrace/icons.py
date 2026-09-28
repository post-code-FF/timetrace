import configparser
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

_DEFAULT_SEARCH_DIRS = [
    Path.home() / ".local" / "share" / "applications",
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
]

_icon_cache: dict[str, object] = {}


def find_desktop_entry(
    resource_class: str, search_dirs: Sequence[Path] | None = None
) -> Path | None:
    dirs = search_dirs if search_dirs is not None else _DEFAULT_SEARCH_DIRS
    target = resource_class.lower()
    # GNOME's Shell.WindowTracker reports app ids as the desktop file's id
    # including the ".desktop" suffix (e.g. "org.mozilla.firefox.desktop"),
    # unlike X11/KDE's bare WM_CLASS -- strip it so the comparisons below
    # (against StartupWMClass, Exec basename, and file stem, none of which
    # carry the suffix) can still match.
    if target.endswith(".desktop"):
        target = target[: -len(".desktop")]
    candidates = []
    for directory in dirs:
        if not directory.is_dir():
            continue
        candidates.extend(sorted(directory.glob("*.desktop")))

    for path in candidates:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except configparser.Error:
            continue
        if not parser.has_section("Desktop Entry"):
            continue
        wm_class = parser.get("Desktop Entry", "StartupWMClass", fallback="")
        if wm_class.lower() == target:
            return path

    for path in candidates:
        parser = configparser.ConfigParser(interpolation=None)
        try:
            parser.read(path, encoding="utf-8")
        except configparser.Error:
            continue
        if not parser.has_section("Desktop Entry"):
            continue
        exec_value = parser.get("Desktop Entry", "Exec", fallback="")
        exec_basename = exec_value.split()[0].rsplit("/", 1)[-1] if exec_value else ""
        if exec_basename.lower() == target or path.stem.lower() == target:
            return path

    return None


def icon_name_from_desktop_entry(entry_path: Path) -> str | None:
    parser = configparser.ConfigParser(interpolation=None)
    parser.read(entry_path, encoding="utf-8")
    return parser.get("Desktop Entry", "Icon", fallback=None)


def resolve_icon(resource_class: str, icon_loader: Callable[[str], object] | None = None):
    if resource_class in _icon_cache:
        return _icon_cache[resource_class]

    loader = icon_loader or _real_icon_loader
    entry = find_desktop_entry(resource_class)
    icon_name = icon_name_from_desktop_entry(entry) if entry else None
    icon = loader(icon_name or "unknown")
    _icon_cache[resource_class] = icon
    return icon


def _real_icon_loader(icon_name: str):
    from PySide6.QtGui import QIcon

    return QIcon.fromTheme(icon_name)
