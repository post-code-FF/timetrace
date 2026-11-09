"""Install the bundled bridge in the user's GNOME 51 session."""
import os
import re
import subprocess
import tempfile
from importlib import resources
from pathlib import Path

from timetrace.subprocess_env import system_subprocess_env

EXTENSION_UUID = "timetrace@timetrace.app"
_RELOGIN = "Расширение TimeTrace установлено. Выйдите из сеанса GNOME и войдите снова, чтобы начать отслеживание окон."


def install_and_enable(extensions_dir: Path | None = None) -> str | None:
    """Return a user-facing notice when setup needs further action."""
    try:
        version = subprocess.run(
            ["gnome-shell", "--version"], capture_output=True, text=True,
            timeout=5, env=system_subprocess_env(),
        )
        major = re.search(r"GNOME Shell (\d+)", version.stdout)
        if version.returncode or not major or major.group(1) != "51":
            return "Расширение TimeTrace этой версии поддерживает GNOME 51. Отслеживание окон недоступно."

        data_home = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share")
        target = (extensions_dir if extensions_dir is not None else data_home / "gnome-shell/extensions") / EXTENSION_UUID
        existed = target.exists()
        target.mkdir(parents=True, exist_ok=True)
        bundled = resources.files("timetrace.assets.gnome_extension")
        changed = False
        for name in ("extension.js", "metadata.json"):
            content = (bundled / name).read_bytes()
            destination = target / name
            if destination.is_file() and destination.read_bytes() == content:
                continue
            with tempfile.NamedTemporaryFile(dir=target, delete=False) as temp:
                temporary = Path(temp.name)
                temp.write(content)
            try:
                temporary.chmod(0o644)
                temporary.replace(destination)
            finally:
                temporary.unlink(missing_ok=True)
            changed = True

        enabled = subprocess.run(
            ["gnome-extensions", "enable", EXTENSION_UUID],
            capture_output=True, text=True, timeout=5, env=system_subprocess_env(),
        )
        if enabled.returncode or (existed and changed):
            return _RELOGIN
        return None
    except (OSError, subprocess.TimeoutExpired):
        return "Не удалось автоматически установить или включить расширение TimeTrace. Проверьте расширения в настройках GNOME."
