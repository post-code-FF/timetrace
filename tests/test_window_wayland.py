import struct
import socket
import time

import pytest

from timetrace.backends.window_wayland import ToplevelTracker


def test_cosmic_metadata_done_does_not_commit_pending_activation():
    output = []
    state = ToplevelTracker(lambda *args: output.append(args))
    handle = object()
    state.add(handle)
    state.update(handle, app_id="browser", title="old", states=struct.pack("=II", 2, 3))
    state.commit_all()
    state.update(handle, title="new", states=b"")
    state.commit_metadata(handle)
    assert output[-1] == ("browser", "new", True)
    state.commit_all()
    assert output[-1] == ("", None, False)


def test_wayland_capability_probe_times_out_on_stalled_compositor(tmp_path, monkeypatch):
    from timetrace.backends.window_wayland import WaylandToplevelClient
    listener = socket.socket(socket.AF_UNIX)
    listener.bind(str(tmp_path / "stalled"))
    listener.listen()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setenv("WAYLAND_DISPLAY", "stalled")
    start = time.monotonic()
    try:
        with pytest.raises(TimeoutError):
            WaylandToplevelClient()
    finally:
        listener.close()
    assert time.monotonic() - start < 2


def test_focus_is_published_only_after_done_and_uses_native_uint_states():
    output = []
    state = ToplevelTracker(lambda *args: output.append(args))
    first, second = object(), object()
    state.add(first)
    state.update(first, app_id="org.test.Editor", title="Document", states=struct.pack("=II", 2, 3))
    assert output == []
    state.commit(first)
    assert output == [("org.test.Editor", "Document", True)]
    state.add(second)
    state.update(second, app_id="terminal", title="shell", states=struct.pack("=I", 2))
    state.commit(second)
    state.update(first, states=b"")
    state.commit(first)
    assert output[-1] == ("terminal", "shell", False)
    state.close(second)
    assert output[-1] == ("", None, False)


def test_title_updates_and_focus_loss_never_restore_stale_window():
    output = []
    state = ToplevelTracker(lambda *args: output.append(args))
    handle = object()
    state.add(handle)
    state.update(handle, app_id="browser", states=struct.pack("=I", 2))
    state.commit(handle)
    state.update(handle, title="new title")
    state.commit(handle)
    assert output[-1] == ("browser", "new title", False)
    state.clear()
    assert output[-1] == ("", None, False)
    state.commit(handle)
    assert output[-1] == ("", None, False)
