from typing import Callable

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget


class TrayIcon(QSystemTrayIcon):
    def __init__(
        self, window: QWidget, on_quit: Callable[[], None], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._on_quit_callback = on_quit
        self.setIcon(QIcon.fromTheme("timetrace"))
        self.setToolTip("TimeTrace")

        menu = QMenu()
        toggle_action = menu.addAction("Показать/Скрыть")
        toggle_action.triggered.connect(self._toggle_window)
        quit_action = menu.addAction("Выход")
        quit_action.triggered.connect(self._on_quit)
        self.setContextMenu(menu)

        self.activated.connect(self._on_activated)

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self._toggle_window()

    def _toggle_window(self) -> None:
        if self._window.isVisible():
            self._window.hide()
        else:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()

    def _on_quit(self) -> None:
        self._on_quit_callback()
