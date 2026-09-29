from timetrace.autostart import is_autostart_enabled, set_autostart_enabled


def test_disabled_when_file_missing(tmp_path):
    path = tmp_path / "timetrace.desktop"
    assert is_autostart_enabled(path) is False


def test_enable_creates_desktop_file_with_exec(tmp_path):
    path = tmp_path / "autostart" / "timetrace.desktop"
    set_autostart_enabled(True, autostart_path=path, exec_path="/usr/bin/timetrace")
    assert path.exists()
    content = path.read_text()
    assert "Exec=/usr/bin/timetrace --minimized" in content
    assert "[Desktop Entry]" in content
    assert is_autostart_enabled(path) is True


def test_disable_removes_desktop_file(tmp_path):
    path = tmp_path / "timetrace.desktop"
    set_autostart_enabled(True, autostart_path=path, exec_path="/usr/bin/timetrace")
    set_autostart_enabled(False, autostart_path=path)
    assert not path.exists()
    assert is_autostart_enabled(path) is False


def test_disable_when_already_absent_does_not_raise(tmp_path):
    path = tmp_path / "timetrace.desktop"
    set_autostart_enabled(False, autostart_path=path)  # must not raise
    assert not path.exists()
