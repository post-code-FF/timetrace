"""Человекочитаемые названия для окон игр.

Steam/Proton отдаёт окну класс ``steam_app_<id>``, Wine — имя exe-файла
(``forzahorizon6.exe``). Здесь такие классы превращаются в настоящие названия
игр: по манифестам Steam, ярлыкам сторонних игр (``shortcuts.vdf``) и
``.desktop``-файлам (Steam, PortProton, Lutris, Bottles и т. п.).
"""

import configparser
import re
from collections.abc import Sequence
from pathlib import Path

_STEAM_APP_RE = re.compile(r"^steam_app_(\d+)$")
_RUNGAMEID_RE = re.compile(r"steam://rungameid/(\d+)")
_ACF_NAME_RE = re.compile(r'"name"\s+"([^"]*)"')
_VDF_PATH_RE = re.compile(r'"path"\s+"([^"]*)"')
_SHORTCUT_RE = re.compile(rb"\x02appid\x00(.{4}).*?\x01appname\x00([^\x00]*)\x00", re.S | re.I)

_HOME = Path.home()
_STEAM_ROOTS = [
    _HOME / ".local" / "share" / "Steam",
    _HOME / ".steam" / "steam",
    _HOME / ".steam" / "root",
    _HOME / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
]
_DESKTOP_DIRS = [
    _HOME / ".local" / "share" / "applications",
    _HOME / "Desktop",
    _HOME / "Рабочий стол",
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
]


class AppNameResolver:
    def __init__(
        self,
        steam_roots: Sequence[Path] | None = None,
        desktop_dirs: Sequence[Path] | None = None,
    ) -> None:
        self._steam_roots = list(steam_roots if steam_roots is not None else _STEAM_ROOTS)
        self._desktop_dirs = list(desktop_dirs if desktop_dirs is not None else _DESKTOP_DIRS)
        self._steam_names: dict[int, str] | None = None
        self._steam_icons: dict[int, str] = {}
        self._exe_names: dict[str, tuple[str, str | None]] = {}
        self._cache: dict[str, str] = {}

    def display_name(self, resource_class: str, window_title: str | None = None) -> str:
        key = f"{resource_class}\0{window_title or ''}"
        cached = self._cache.get(key)
        if cached is None:
            cached = self._resolve(resource_class, window_title)
            self._cache[key] = cached
        return cached

    def icon_name(self, resource_class: str) -> str | None:
        """Имя иконки из .desktop-файла игры Steam (steam_icon_<id>)."""
        match = _STEAM_APP_RE.match(resource_class)
        if not match:
            return None
        self._load()
        return self._steam_icons.get(int(match.group(1)))

    def _resolve(self, resource_class: str, window_title: str | None) -> str:
        match = _STEAM_APP_RE.match(resource_class)
        if match:
            self._load()
            name = self._steam_names.get(int(match.group(1)))
            if name:
                return name
            title = (window_title or "").strip()
            return title or f"Steam App {match.group(1)}"
        if resource_class.lower().endswith(".exe"):
            self._load()
            known = self._exe_names.get(resource_class.lower())
            if known:
                return known[0]
            return resource_class[: -len(".exe")]
        return resource_class

    def _load(self) -> None:
        if self._steam_names is not None:
            return
        names: dict[int, str] = {}
        self._steam_names = names
        for root in self._steam_roots:
            self._load_steam_root(root, names)
        for directory in self._desktop_dirs:
            self._load_desktop_dir(directory, names)

    def _load_steam_root(self, root: Path, names: dict[int, str]) -> None:
        libraries = [root / "steamapps"]
        try:
            vdf = (root / "steamapps" / "libraryfolders.vdf").read_text(errors="replace")
            libraries += [Path(p) / "steamapps" for p in _VDF_PATH_RE.findall(vdf)]
        except OSError:
            pass
        for library in libraries:
            try:
                manifests = list(library.glob("appmanifest_*.acf"))
            except OSError:
                continue
            for manifest in manifests:
                try:
                    app_id = int(manifest.stem.split("_", 1)[1])
                    text = manifest.read_text(errors="replace")
                except (OSError, ValueError, IndexError):
                    continue
                found = _ACF_NAME_RE.search(text)
                if found and found.group(1):
                    names.setdefault(app_id, found.group(1))
        try:
            shortcut_files = list((root / "userdata").glob("*/config/shortcuts.vdf"))
        except OSError:
            shortcut_files = []
        for shortcuts in shortcut_files:
            try:
                data = shortcuts.read_bytes()
            except OSError:
                continue
            for raw_id, raw_name in _SHORTCUT_RE.findall(data):
                name = raw_name.decode("utf-8", errors="replace")
                if name:
                    names.setdefault(int.from_bytes(raw_id, "little"), name)

    def _load_desktop_dir(self, directory: Path, names: dict[int, str]) -> None:
        try:
            entries = sorted(directory.rglob("*.desktop"))
        except OSError:
            return
        for path in entries:
            parser = configparser.ConfigParser(interpolation=None, strict=False)
            try:
                parser.read(path, encoding="utf-8")
            except (configparser.Error, UnicodeDecodeError, OSError):
                continue
            if not parser.has_section("Desktop Entry"):
                continue
            entry = parser["Desktop Entry"]
            name = entry.get("Name", "").strip()
            exec_line = entry.get("Exec", "")
            if not name or not exec_line:
                continue
            icon = entry.get("Icon") or None
            game = _RUNGAMEID_RE.search(exec_line)
            if game:
                game_id = int(game.group(1))
                # Для сторонних игр Steam ярлык хранит 64-битный id, а окно
                # получает класс по старшим 32 битам (appid).
                app_id = game_id >> 32 if game_id > 0xFFFFFFFF else game_id
                names.setdefault(app_id, name)
                if icon:
                    self._steam_icons.setdefault(app_id, icon)
                continue
            for exe in re.findall(r"([^\s/\\\"']+\.exe)\b", exec_line, re.I):
                self._exe_names.setdefault(exe.lower(), (name, icon))


_default = AppNameResolver()


def display_name(resource_class: str, window_title: str | None = None) -> str:
    return _default.display_name(resource_class, window_title)


def steam_icon_name(resource_class: str) -> str | None:
    return _default.icon_name(resource_class)
