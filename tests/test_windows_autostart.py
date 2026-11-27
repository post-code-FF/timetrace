import sys

import pytest

from timetrace import autostart


class FakeKey:
    def __init__(self):
        self.values = {}
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


@pytest.mark.skipif(sys.platform != "win32", reason="Windows registry integration")
def test_windows_autostart_writes_and_removes_run_value(monkeypatch, tmp_path):
    key = FakeKey()
    opened = []
    deleted = []
    written = []
    monkeypatch.setattr(autostart.winreg, "OpenKey", lambda *args: opened.append(args) or key)
    monkeypatch.setattr(autostart.winreg, "SetValueEx", lambda *args: written.append(args))
    monkeypatch.setattr(autostart.winreg, "DeleteValue", lambda *args: deleted.append(args))
    monkeypatch.setattr(autostart.winreg, "QueryValueEx", lambda *args: ("", 1))
    exe = tmp_path / "Time Trace.exe"

    autostart.set_autostart_enabled(True, exec_path=str(exe))
    assert autostart.is_autostart_enabled() is True
    assert written[-1][1] == "TimeTrace"
    assert written[-1][4] == f'"{exe}" --minimized'

    autostart.set_autostart_enabled(False)
    assert deleted[-1][1] == "TimeTrace"
    assert key.closed