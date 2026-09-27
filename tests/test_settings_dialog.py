from timetrace.config import Config, load_config
from timetrace.ui.settings_dialog import SettingsDialog


def test_dialog_initializes_controls_from_config(qtbot):
    config = Config(autostart=True, theme="dark", idle_threshold_minutes=10)
    dialog = SettingsDialog(
        config,
        config_path=None,  # not written to in this test
        on_idle_threshold_changed=lambda m: None,
        on_theme_changed=lambda t: None,
    )
    qtbot.addWidget(dialog)
    assert dialog._autostart_checkbox.isChecked() is True
    assert dialog._theme_dark_radio.isChecked() is True
    assert dialog._idle_spinbox.value() == 10


def test_accept_persists_config_and_invokes_callbacks(qtbot, tmp_path):
    config_path = tmp_path / "config.toml"
    theme_calls = []
    threshold_calls = []
    dialog = SettingsDialog(
        Config(),
        config_path=config_path,
        on_idle_threshold_changed=lambda m: threshold_calls.append(m),
        on_theme_changed=lambda t: theme_calls.append(t),
        exec_path="/usr/bin/timetrace",
    )
    qtbot.addWidget(dialog)

    dialog._autostart_checkbox.setChecked(True)
    dialog._theme_dark_radio.setChecked(True)
    dialog._idle_spinbox.setValue(15)
    dialog.accept()

    saved = load_config(config_path)
    assert saved.autostart is True
    assert saved.theme == "dark"
    assert saved.idle_threshold_minutes == 15
    assert theme_calls == ["dark"]
    assert threshold_calls == [15]


def test_accept_toggles_autostart_file(qtbot, tmp_path):
    config_path = tmp_path / "config.toml"
    autostart_path = tmp_path / "autostart" / "timetrace.desktop"
    dialog = SettingsDialog(
        Config(),
        config_path=config_path,
        on_idle_threshold_changed=lambda m: None,
        on_theme_changed=lambda t: None,
        exec_path="/usr/bin/timetrace",
        autostart_path=autostart_path,
    )
    qtbot.addWidget(dialog)
    dialog._autostart_checkbox.setChecked(True)
    dialog.accept()
    assert autostart_path.exists()
