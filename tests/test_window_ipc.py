import json
import socket
import threading

import pytest

from timetrace.backends.window_ipc import HyprlandReader, NiriReader, PollingWindowBackend


@pytest.fixture
def server(tmp_path):
    threads = []
    sockets = []

    def start(response, expected):
        path = str(tmp_path / f"socket-{len(sockets)}")
        listener = socket.socket(socket.AF_UNIX)
        listener.bind(path)
        listener.listen()
        listener.settimeout(2)
        sockets.append(listener)

        def serve():
            conn, _ = listener.accept()
            with conn:
                assert conn.recv(4096) == expected
                data = json.dumps(response).encode() + b"\n"
                conn.sendall(data[:5])
                conn.sendall(data[5:])
        thread = threading.Thread(target=serve)
        threads.append(thread)
        thread.start()
        return path

    yield start
    for thread in threads:
        thread.join(timeout=3)
        assert not thread.is_alive()
    for listener in sockets:
        listener.close()


def test_hyprland_json_preserves_commas_unicode_and_fullscreen(server):
    path = server({"class": "firefox", "title": "Привет, мир", "fullscreen": 2}, b"j/activewindow")
    assert HyprlandReader(path)() == ("firefox", "Привет, мир", True)


@pytest.mark.parametrize("mode,fullscreen", [(0, False), (1, False), (2, True), (False, False), (True, True)])
def test_hyprland_maximized_window_does_not_exempt_idle(server, mode, fullscreen):
    path = server({"class": "editor", "title": "file", "fullscreen": mode}, b"j/activewindow")
    assert HyprlandReader(path)() == ("editor", "file", fullscreen)


def test_niri_handles_focused_window_and_empty_workspace(server):
    path = server({"Ok": {"FocusedWindow": {"app_id": "terminal", "title": None}}}, b'"FocusedWindow"\n')
    assert NiriReader(path)() == ("terminal", None, False)
    path = server({"Ok": {"FocusedWindow": None}}, b'"FocusedWindow"\n')
    assert NiriReader(path)() == ("", None, False)


def test_niri_error_is_not_misreported_as_active(server):
    path = server({"Err": "not ready"}, b'"FocusedWindow"\n')
    with pytest.raises(ValueError):
        NiriReader(path)()


def test_disconnect_clears_foreground_then_recovers_and_stop_joins():
    failed = threading.Event()
    recovered = threading.Event()
    outputs = []
    steps = iter([("first", "a", True), OSError("disconnected"), ("second", "b", False)])

    def read():
        value = next(steps, ("second", "b", False))
        if isinstance(value, Exception):
            raise value
        return value

    def accept(app, title, ts):
        outputs.append((app, title))
        if app == "":
            failed.set()
        if app == "second":
            recovered.set()

    backend = PollingWindowBackend(read, interval=0.01)
    backend.start(accept)
    assert failed.wait(2)
    assert recovered.wait(2)
    backend.stop()
    assert outputs[:3] == [("first", "a"), ("", None), ("second", "b")]
    assert not backend._thread.is_alive()
