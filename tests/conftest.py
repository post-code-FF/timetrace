import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


def pytest_collection_modifyitems(config, items):
    if sys.platform != "win32":
        return
    linux_only = pytest.mark.skip(reason="Linux-only desktop/package integration")
    for item in items:
        path = item.path.name
        if path in {
            "test_package_launcher.py", "test_package_restart.py",
            "test_window_wayland.py", "test_window_ipc.py",
            "test_idle_kde_wayland.py", "test_gnome_extension.py",
            "test_session_gnome.py", "test_session_cinnamon.py",
            "test_window_kwin.py", "test_idle_gnome.py",
            "test_window_factory.py", "test_main_bootstrap.py",
        } or (path == "test_icons.py" and item.name in {
            "test_nested_desktop_id_and_env_wrapped_exec",
            "test_xdg_and_flatpak_discovery",
        }):
            item.add_marker(linux_only)


@pytest.fixture(autouse=True)
def isolated_xdg_dirs(tmp_path, monkeypatch):
    # UI tests may toggle autostart. Never write the real user's settings.
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path / 'xdg-config'))
    monkeypatch.setenv('XDG_DATA_HOME', str(tmp_path / 'xdg-data'))
