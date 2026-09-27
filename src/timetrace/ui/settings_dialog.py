from pathlib import Path
from typing import Callable

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from timetrace.autostart import set_autostart_enabled
from timetrace.config import Config, save_config


class SettingsDialog(QDialog):
    def __init__(
        self,
        config: Config,
        config_path: Path | None,
        on_idle_threshold_changed: Callable[[int], None],
        on_theme_changed: Callable[[str], None],
        exec_path: str | None = None,
        autostart_path: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self._config_path = config_path
        self._on_idle_threshold_changed = on_idle_threshold_changed
        self._on_theme_changed = on_theme_changed
        self._exec_path = exec_path
        self._autostart_path = autostart_path

        self._autostart_checkbox = QCheckBox("Автозагрузка")
        self._autostart_checkbox.setChecked(config.autostart)

        self._theme_light_radio = QRadioButton("Светлая")
        self._theme_dark_radio = QRadioButton("Тёмная")
        self._theme_system_radio = QRadioButton("Синхронизировать с ОС")
        {"light": self._theme_light_radio, "dark": self._theme_dark_radio, "system": self._theme_system_radio}[
            config.theme
        ].setChecked(True)
        theme_row = QHBoxLayout()
        theme_row.addWidget(self._theme_light_radio)
        theme_row.addWidget(self._theme_dark_radio)
        theme_row.addWidget(self._theme_system_radio)
        theme_widget = QWidget()
        theme_widget.setLayout(theme_row)

        self._idle_spinbox = QSpinBox()
        self._idle_spinbox.setRange(1, 120)
        self._idle_spinbox.setValue(config.idle_threshold_minutes)

        form = QFormLayout()
        form.addRow(self._autostart_checkbox)
        form.addRow("Тема:", theme_widget)
        form.addRow("Порог простоя (мин):", self._idle_spinbox)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _selected_theme(self) -> str:
        if self._theme_dark_radio.isChecked():
            return "dark"
        if self._theme_system_radio.isChecked():
            return "system"
        return "light"

    def accept(self) -> None:
        new_config = Config(
            autostart=self._autostart_checkbox.isChecked(),
            theme=self._selected_theme(),
            idle_threshold_minutes=self._idle_spinbox.value(),
        )
        if self._config_path is not None:
            save_config(self._config_path, new_config)
        set_autostart_enabled(
            new_config.autostart,
            autostart_path=self._autostart_path,
            exec_path=self._exec_path,
        )
        self._on_theme_changed(new_config.theme)
        self._on_idle_threshold_changed(new_config.idle_threshold_minutes)
        super().accept()
