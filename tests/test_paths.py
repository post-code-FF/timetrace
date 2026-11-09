from pathlib import Path

from timetrace import paths


def test_config_dir_uses_xdg_config_home():
    env = {"XDG_CONFIG_HOME": "/tmp/xdgcfg"}
    assert paths.config_dir(env) == Path("/tmp/xdgcfg/timetrace-gnome-fork")


def test_config_dir_falls_back_to_home_config():
    env = {"HOME": "/home/u"}
    assert paths.config_dir(env) == Path("/home/u/.config/timetrace-gnome-fork")


def test_data_dir_uses_xdg_data_home():
    env = {"XDG_DATA_HOME": "/tmp/xdgdata"}
    assert paths.data_dir(env) == Path("/tmp/xdgdata/timetrace-gnome-fork")


def test_data_dir_falls_back_to_home_local_share():
    env = {"HOME": "/home/u"}
    assert paths.data_dir(env) == Path("/home/u/.local/share/timetrace-gnome-fork")


def test_derived_file_paths():
    env = {"HOME": "/home/u"}
    assert paths.config_file_path(env) == Path("/home/u/.config/timetrace-gnome-fork/config.toml")
    assert paths.db_file_path(env) == Path("/home/u/.local/share/timetrace-gnome-fork/data.db")
    assert paths.autostart_dir(env) == Path("/home/u/.config/autostart")
    assert paths.autostart_file_path(env) == Path("/home/u/.config/autostart/timetrace-gnome-fork.desktop")
