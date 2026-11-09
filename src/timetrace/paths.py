import os
from collections.abc import Mapping
from pathlib import Path

APP_SLUG = "timetrace"


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def config_dir(env: Mapping[str, str] | None = None) -> Path:
    e = _env(env)
    base = e.get("XDG_CONFIG_HOME") or str(Path(e["HOME"]) / ".config")
    return Path(base) / APP_SLUG


def data_dir(env: Mapping[str, str] | None = None) -> Path:
    e = _env(env)
    base = e.get("XDG_DATA_HOME") or str(Path(e["HOME"]) / ".local" / "share")
    return Path(base) / APP_SLUG


def config_file_path(env: Mapping[str, str] | None = None) -> Path:
    return config_dir(env) / "config.toml"


def db_file_path(env: Mapping[str, str] | None = None) -> Path:
    return data_dir(env) / "data.db"


def autostart_dir(env: Mapping[str, str] | None = None) -> Path:
    e = _env(env)
    base = e.get("XDG_CONFIG_HOME") or str(Path(e["HOME"]) / ".config")
    return Path(base) / "autostart"


def autostart_file_path(env: Mapping[str, str] | None = None) -> Path:
    return autostart_dir(env) / f"{APP_SLUG}.desktop"
