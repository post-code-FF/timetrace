# tests/test_theme.py
from timetrace.theme import read_system_color_scheme, watch_system_color_scheme


def test_reads_light_scheme():
    assert read_system_color_scheme(reader=lambda: 0) == "light"


def test_reads_dark_scheme():
    assert read_system_color_scheme(reader=lambda: 1) == "dark"


def test_unknown_value_maps_to_unknown():
    assert read_system_color_scheme(reader=lambda: 2) == "unknown"


def test_reader_raising_maps_to_unknown():
    def broken_reader():
        raise RuntimeError("no portal available")

    assert read_system_color_scheme(reader=broken_reader) == "unknown"


def test_watch_forwards_changes_and_unsubscribe_stops_forwarding():
    handlers = []

    def fake_subscriber(handler):
        handlers.append(handler)
        return lambda: handlers.remove(handler)

    events = []
    unsubscribe = watch_system_color_scheme(
        on_change=lambda scheme: events.append(scheme), subscriber=fake_subscriber
    )
    assert len(handlers) == 1

    handlers[0](1)  # portal reports "dark"
    assert events == ["dark"]

    unsubscribe()
    assert handlers == []


# --- apply_theme -----------------------------------------------------------
import pytest
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from timetrace import theme


def _os_palette(window: QColor, text: QColor) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.Window, window)
    palette.setColor(QPalette.WindowText, text)
    palette.setColor(QPalette.Base, window)
    palette.setColor(QPalette.Text, text)
    palette.setColor(QPalette.Button, window)
    palette.setColor(QPalette.ButtonText, text)
    return palette


DARK_OS = _os_palette(QColor(42, 46, 50), QColor(252, 252, 252))
LIGHT_OS = _os_palette(QColor(239, 240, 241), QColor(35, 38, 41))


@pytest.fixture
def app():
    app = QApplication.instance() or QApplication([])
    original = app.palette()
    yield app
    # Сбрасываем состояние между тестами: apply_theme запоминает палитру ОС на app.
    if hasattr(app, "_timetrace_os_palette"):
        del app._timetrace_os_palette
    app.setPalette(original)


def _install_os_palette(app, palette: QPalette) -> None:
    if hasattr(app, "_timetrace_os_palette"):
        del app._timetrace_os_palette
    app.setPalette(palette)


def _window_lightness(app) -> int:
    return app.palette().color(QPalette.Window).lightness()


def test_light_theme_is_light_even_when_os_theme_is_dark(app):
    _install_os_palette(app, DARK_OS)
    theme.apply_theme(app, "light")
    assert _window_lightness(app) > 200
    assert app.palette().color(QPalette.WindowText).lightness() < 80


def test_dark_theme_is_dark_even_when_os_theme_is_light(app):
    _install_os_palette(app, LIGHT_OS)
    theme.apply_theme(app, "dark")
    assert _window_lightness(app) < 80
    assert app.palette().color(QPalette.WindowText).lightness() > 180


def test_switching_back_and_forth_changes_palette_every_time(app):
    _install_os_palette(app, DARK_OS)
    seen = []
    for mode in ("light", "dark", "light"):
        theme.apply_theme(app, mode)
        seen.append(_window_lightness(app))
    assert seen[0] > 200 and seen[1] < 80 and seen[2] > 200


def test_system_mode_follows_detected_scheme(app, monkeypatch):
    _install_os_palette(app, LIGHT_OS)
    monkeypatch.setattr(theme, "read_system_color_scheme", lambda: "dark")
    theme.apply_theme(app, "system")
    assert _window_lightness(app) < 80
    monkeypatch.setattr(theme, "read_system_color_scheme", lambda: "light")
    theme.apply_theme(app, "system")
    assert _window_lightness(app) > 200


def test_system_mode_without_portal_keeps_os_palette(app, monkeypatch):
    """Портал недоступен -> не гадаем, а оставляем палитру, с которой стартовала ОС."""
    _install_os_palette(app, DARK_OS)
    monkeypatch.setattr(theme, "read_system_color_scheme", lambda: "unknown")
    theme.apply_theme(app, "light")  # меняем руками...
    theme.apply_theme(app, "system")  # ...и возвращаемся к системной
    assert app.palette().color(QPalette.Window) == DARK_OS.color(QPalette.Window)


_ALL_GROUPS = (QPalette.Active, QPalette.Inactive, QPalette.Disabled)
_REQUIRED_ROLES = (
    QPalette.Window, QPalette.WindowText, QPalette.Base, QPalette.AlternateBase,
    QPalette.ToolTipBase, QPalette.ToolTipText, QPalette.Text, QPalette.Button,
    QPalette.ButtonText, QPalette.BrightText, QPalette.Highlight,
    QPalette.HighlightedText, QPalette.Link, QPalette.LinkVisited,
    QPalette.PlaceholderText, QPalette.Light, QPalette.Midlight, QPalette.Mid,
    QPalette.Dark, QPalette.Shadow,
)


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_explicit_theme_defines_every_role_itself(app, mode):
    """Явная тема не должна зависеть от палитры платформы.

    Если роль не задана, Qt подставляет её из палитры платформы (в KDE — из
    kdeglobals), и на тёмной схеме ОС «светлая» тема остаётся тёмной.
    """
    _install_os_palette(app, DARK_OS)
    theme.apply_theme(app, mode)
    palette = app.palette()
    missing = [
        (group, role)
        for group in _ALL_GROUPS
        for role in _REQUIRED_ROLES
        if not palette.isBrushSet(group, role)
    ]
    assert missing == []
