import sys
from pathlib import Path

from timetrace import paths

if sys.platform == "win32":
    import winreg

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "TimeTrace"


def _windows_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _RUN_VALUE)
            return True
    except FileNotFoundError:
        return False


def _set_windows_autostart(enabled: bool, exec_path: str | None) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            executable = exec_path or sys.executable
            winreg.SetValueEx(key, _RUN_VALUE, 0, winreg.REG_SZ, f'"{executable}" --minimized')
        else:
            try:
                winreg.DeleteValue(key, _RUN_VALUE)
            except FileNotFoundError:
                pass


def is_autostart_enabled(autostart_path: Path | None = None) -> bool:
    if sys.platform == "win32" and autostart_path is None:
        return _windows_autostart_enabled()
    path = autostart_path or paths.autostart_file_path()
    return path.exists()


def set_autostart_enabled(
    enabled: bool,
    autostart_path: Path | None = None,
    exec_path: str | None = None,
) -> None:
    if sys.platform == "win32" and autostart_path is None:
        _set_windows_autostart(enabled, exec_path)
        return
    path = autostart_path or paths.autostart_file_path()
    if not enabled:
        path.unlink(missing_ok=True)
        return

    exec_path = exec_path or "timetrace"
    path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=TimeTrace\n"
        f"Exec={exec_path} --minimized\n"
        "X-GNOME-Autostart-enabled=true\n"
    )
    path.write_text(content)
