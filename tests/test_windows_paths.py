import sys
from pathlib import Path

import pytest

from timetrace import paths


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path integration")
def test_windows_paths_use_user_appdata(monkeypatch, tmp_path):
    roaming = tmp_path / "Roaming Profile"
    local = tmp_path / "Local Данные"
    monkeypatch.setenv("APPDATA", str(roaming))
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    assert paths.config_dir() == roaming / "TimeTrace"
    assert paths.data_dir() == local / "TimeTrace"
    assert paths.config_file_path() == roaming / "TimeTrace" / "config.toml"
    assert paths.db_file_path() == local / "TimeTrace" / "data.db"


@pytest.mark.skipif(sys.platform != "win32", reason="Windows path integration")
def test_windows_paths_fallback_to_home(monkeypatch, tmp_path):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    assert paths.config_dir() == tmp_path / "AppData" / "Roaming" / "TimeTrace"
    assert paths.data_dir() == tmp_path / "AppData" / "Local" / "TimeTrace"