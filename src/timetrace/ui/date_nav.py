# src/timetrace/ui/date_nav.py
from datetime import date, timedelta
from typing import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class DateNavigationState:
    def __init__(self, selected: date, today_provider: Callable[[], date] | None = None) -> None:
        self._selected = selected
        self._today_provider = today_provider or date.today

    @property
    def selected(self) -> date:
        return self._selected

    @property
    def can_go_forward(self) -> bool:
        return self._selected < self._today_provider()

    def go_previous(self) -> None:
        self._selected -= timedelta(days=1)

    def go_next(self) -> None:
        if self.can_go_forward:
            self._selected += timedelta(days=1)

    def go_today(self) -> None:
        self._selected = self._today_provider()


class DateNavBar(QWidget):
    dateChanged = Signal(date)

    def __init__(self, initial: date | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._state = DateNavigationState(initial or date.today())

        self._prev_button = QPushButton("<")
        self._today_button = QPushButton("Сегодня")
        self._next_button = QPushButton(">")
        self._label = QLabel()

        layout = QHBoxLayout(self)
        layout.addWidget(self._prev_button)
        layout.addWidget(self._label)
        layout.addWidget(self._today_button)
        layout.addWidget(self._next_button)

        self._prev_button.clicked.connect(self._on_previous)
        self._next_button.clicked.connect(self._on_next)
        self._today_button.clicked.connect(self._on_today)

        self._refresh()

    def _on_previous(self) -> None:
        self._state.go_previous()
        self._refresh()
        self.dateChanged.emit(self._state.selected)

    def _on_next(self) -> None:
        self._state.go_next()
        self._refresh()
        self.dateChanged.emit(self._state.selected)

    def _on_today(self) -> None:
        self._state.go_today()
        self._refresh()
        self.dateChanged.emit(self._state.selected)

    def _refresh(self) -> None:
        self._label.setText(self._state.selected.isoformat())
        self._next_button.setEnabled(self._state.can_go_forward)

    def selected_date(self) -> date:
        return self._state.selected
