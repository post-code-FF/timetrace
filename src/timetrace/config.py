import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Theme = Literal["light", "dark", "system"]


@dataclass
class Config:
    autostart: bool = False
    theme: Theme = "system"
    idle_threshold_minutes: int = 5


def load_config(path: Path) -> Config:
    if not path.exists():
        return Config()
    with path.open("rb") as f:
        data = tomllib.load(f)
    return Config(
        autostart=bool(data.get("autostart", False)),
        theme=data.get("theme", "system"),
        idle_threshold_minutes=int(data.get("idle_threshold_minutes", 5)),
    )


def save_config(path: Path, config: Config) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"autostart = {'true' if config.autostart else 'false'}",
        f'theme = "{config.theme}"',
        f"idle_threshold_minutes = {config.idle_threshold_minutes}",
    ]
    path.write_text("\n".join(lines) + "\n")
