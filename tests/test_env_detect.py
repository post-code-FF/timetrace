# tests/test_env_detect.py
from timetrace.env_detect import detect_desktop_environment, detect_session_type


def test_detects_kde():
    assert detect_desktop_environment({"XDG_CURRENT_DESKTOP": "KDE"}) == "kde"


def test_detects_gnome():
    assert detect_desktop_environment({"XDG_CURRENT_DESKTOP": "GNOME"}) == "gnome"


def test_detects_gnome_from_compound_value():
    assert detect_desktop_environment({"XDG_CURRENT_DESKTOP": "ubuntu:GNOME"}) == "gnome"


def test_unknown_desktop_is_other():
    assert detect_desktop_environment({"XDG_CURRENT_DESKTOP": "XFCE"}) == "other"


def test_missing_env_var_is_other():
    assert detect_desktop_environment({}) == "other"


def test_detects_wayland_session():
    assert detect_session_type({"XDG_SESSION_TYPE": "wayland"}) == "wayland"


def test_detects_x11_session():
    assert detect_session_type({"XDG_SESSION_TYPE": "x11"}) == "x11"


def test_falls_back_to_wayland_display_var():
    assert detect_session_type({"WAYLAND_DISPLAY": "wayland-0"}) == "wayland"


def test_falls_back_to_display_var():
    assert detect_session_type({"DISPLAY": ":0"}) == "x11"


def test_unknown_session_when_nothing_set():
    assert detect_session_type({}) == "unknown"
