from pathlib import Path

from timetrace import paths


def is_autostart_enabled(autostart_path: Path | None = None) -> bool:
    path = autostart_path or paths.autostart_file_path()
    return path.exists()


def set_autostart_enabled(
    enabled: bool,
    autostart_path: Path | None = None,
    exec_path: str | None = None,
) -> None:
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
