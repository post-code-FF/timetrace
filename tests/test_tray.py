from PySide6.QtWidgets import QWidget

from timetrace.ui.tray import TrayIcon


def test_activation_toggles_window_visibility(qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    window.show()

    tray = TrayIcon(window, on_quit=lambda: None)
    tray._toggle_window()
    assert window.isVisible() is False
    tray._toggle_window()
    assert window.isVisible() is True


def test_quit_action_invokes_callback(qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    calls = []
    tray = TrayIcon(window, on_quit=lambda: calls.append(True))
    tray._on_quit()
    assert calls == [True]


def test_menu_has_toggle_and_quit_actions(qtbot):
    window = QWidget()
    qtbot.addWidget(window)
    tray = TrayIcon(window, on_quit=lambda: None)
    action_texts = [a.text() for a in tray.contextMenu().actions()]
    assert "Показать/Скрыть" in action_texts
    assert "Выход" in action_texts
