"""Shared discovery of installed applications (XDG, Flatpak and Snap)."""

import configparser
import os
import shlex
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from time import monotonic


def data_dirs() -> list[Path]:
    home = Path.home()
    paths = [Path(os.environ.get('XDG_DATA_HOME') or home / '.local/share')]
    paths += [Path(p) for p in (os.environ.get('XDG_DATA_DIRS') or '/usr/local/share:/usr/share').split(':') if p]
    paths += [home / '.local/share/flatpak/exports/share', Path('/var/lib/flatpak/exports/share'), Path('/var/lib/snapd/desktop')]
    return list(dict.fromkeys(p for p in paths if p.is_absolute()))


def application_dirs() -> list[Path]:
    return [p / 'applications' for p in data_dirs()]


def read_entry(path: Path) -> dict[str, str]:
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    try:
        parser.read(path, encoding='utf-8')
        return dict(parser['Desktop Entry']) if parser.has_section('Desktop Entry') else {}
    except (configparser.Error, UnicodeError, OSError):
        return {}


def _executable(command: str) -> str:
    try:
        args = shlex.split(command)
    except ValueError:
        return ''
    if args and Path(args[0]).name == 'env':
        args = args[1:]
        while args and ('=' in args[0] or args[0].startswith('-')):
            args.pop(0)
    if not args or 'steam://rungameid/' in command:
        return ''
    if Path(args[0]).name == 'flatpak':
        return ''  # Match X-Flatpak / desktop id, never all Flatpak apps.
    if Path(args[0]).name == 'snap' and len(args) > 2 and args[1] == 'run':
        return args[2]
    return Path(args[0]).name


@dataclass
class DesktopEntry:
    path: Path
    desktop_id: str
    values: dict[str, str]

    def name(self) -> str | None:
        language = next((os.environ[k] for k in ('LC_ALL', 'LC_MESSAGES', 'LANG') if os.environ.get(k)), '')
        language = language.split('.')[0]
        variants = [language, language.split('@')[0], language.split('_')[0]]
        for variant in variants:
            if value := self.values.get(f'Name[{variant}]'):
                return value
        return self.values.get('Name') or None


def entries(dirs: tuple[Path, ...]) -> list[DesktopEntry]:
    return _entries(dirs, int(monotonic() // 30))


@lru_cache(maxsize=8)
def _entries(dirs: tuple[Path, ...], generation: int) -> list[DesktopEntry]:
    result = []
    seen = set()
    for directory in dirs:
        try:
            paths = sorted(directory.rglob('*.desktop'))
        except OSError:
            continue
        for path in paths:
            desktop_id = str(path.relative_to(directory)).replace('/', '-')[:-8]
            if desktop_id in seen:
                continue
            values = read_entry(path)
            if not values:
                continue
            seen.add(desktop_id)
            if values.get('Hidden', '').lower() == 'true':
                continue
            if values.get('Type', 'Application') != 'Application':
                continue
            result.append(DesktopEntry(path, desktop_id, values))
    return result


def find_entry(resource_class: str, search_dirs=None) -> DesktopEntry | None:
    target = resource_class.casefold()
    if not target:
        return None
    candidates = entries(tuple(application_dirs() if search_dirs is None else search_dirs))
    # A literal id can itself end in .desktop (Telegram does this).
    for key in dict.fromkeys([target, target.removesuffix('.desktop')]):
        for entry in candidates:
            if entry.desktop_id.casefold() == key:
                return entry
    target = target.removesuffix('.desktop')
    for field in ('StartupWMClass', 'X-Flatpak', 'X-SnapInstanceName'):
        for entry in candidates:
            if entry.values.get(field, '').casefold() == target:
                return entry
    for entry in candidates:
        if _executable(entry.values.get('Exec', '')).casefold() == target:
            return entry
    return None
