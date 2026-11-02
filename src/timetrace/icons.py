from glob import escape
from collections.abc import Sequence
from pathlib import Path
from typing import Callable

from timetrace.desktop_entries import data_dirs, find_entry, read_entry

_icon_cache: dict[str, object] = {}


def find_desktop_entry(resource_class: str, search_dirs: Sequence[Path] | None = None) -> Path | None:
    entry = find_entry(resource_class, search_dirs)
    return entry.path if entry else None


def icon_name_from_desktop_entry(entry_path: Path) -> str | None:
    return read_entry(entry_path).get("Icon") or None


def resolve_icon(resource_class: str, icon_loader: Callable[[str], object] | None = None):
    if resource_class in _icon_cache:
        return _icon_cache[resource_class]

    loader = icon_loader or _real_icon_loader
    from timetrace.app_names import steam_icon_name

    entry = find_desktop_entry(resource_class)
    icon_name = icon_name_from_desktop_entry(entry) if entry else None
    if icon_name is None:
        icon_name = steam_icon_name(resource_class)
    icon = loader(icon_name or resource_class.removesuffix(".desktop"))
    if icon_loader is None and icon.pixmap(24, 24).isNull():
        icon = _fallback_icon()
    _icon_cache[resource_class] = icon
    return icon


def _real_icon_loader(icon_name: str):
    from PySide6.QtGui import QIcon

    path = Path(icon_name)
    if path.is_absolute():
        return QIcon(str(path))
    icon = QIcon.fromTheme(icon_name)
    if not icon.pixmap(24, 24).isNull():
        return icon
    # Frozen Qt and minimal desktops may not know the host icon theme.
    # Search exported icon roots and pixmaps as well, including Flatpak/Snap.
    roots = [Path.home() / ".icons"] + [p / "icons" for p in data_dirs()]
    for root in roots:
        for suffix in ("", ".png", ".svg", ".svgz", ".xpm"):
            filename = icon_name + suffix
            if "/" in filename or filename in (".", ".."):
                continue
            for candidate in sorted(root.glob(f"*/*/*/{escape(filename)}")) + [root / filename]:
                if candidate.is_file():
                    found = QIcon(str(candidate))
                    if not found.pixmap(24, 24).isNull():
                        return found
    for root in data_dirs():
        for suffix in ("", ".png", ".svg", ".svgz", ".xpm"):
            candidate = root / "pixmaps" / (icon_name + suffix)
            if candidate.is_file():
                found = QIcon(str(candidate))
                if not found.pixmap(24, 24).isNull():
                    return found
    return icon


def _fallback_icon():
    from importlib import resources
    from PySide6.QtGui import QIcon

    return QIcon(str(resources.files("timetrace.assets") / "application.svg"))


def app_icon():
    """Иконка приложения: встроенный файл, а если его нет — иконка из темы."""
    from importlib import resources

    from PySide6.QtGui import QIcon

    icon_file = resources.files("timetrace.assets") / "icon.png"
    if icon_file.is_file():
        return QIcon(str(icon_file))
    return QIcon.fromTheme("timetrace")
