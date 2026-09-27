from pathlib import Path

from timetrace.config import Config, load_config, save_config


def test_defaults():
    c = Config()
    assert c.autostart is False
    assert c.theme == "system"
    assert c.idle_threshold_minutes == 5


def test_load_missing_file_returns_defaults(tmp_path):
    missing = tmp_path / "does-not-exist" / "config.toml"
    c = load_config(missing)
    assert c == Config()


def test_save_then_load_round_trip(tmp_path):
    path = tmp_path / "config.toml"
    original = Config(autostart=True, theme="dark", idle_threshold_minutes=10)
    save_config(path, original)
    loaded = load_config(path)
    assert loaded == original


def test_save_creates_parent_directories(tmp_path):
    path = tmp_path / "nested" / "dir" / "config.toml"
    save_config(path, Config())
    assert path.exists()
