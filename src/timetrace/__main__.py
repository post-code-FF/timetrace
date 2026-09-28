import sys
from datetime import datetime, timezone
from typing import Optional

from . import __version__


def _make_single_instance_adaptor(on_raise):
    """QObject exposing Raise() as a Qt slot so a second TimeTrace process
    can ask this one to show its window. Same ExportAllSlots pattern as
    Task 12's `_TimeTraceDBusAdaptor`; verify the exact registerObject call
    against the installed PySide6 version when implementing."""
    from PySide6.QtCore import QObject, Slot

    class _SingleInstanceAdaptor(QObject):
        @Slot()
        def Raise(self) -> None:
            on_raise()

    return _SingleInstanceAdaptor()


def build_app(argv: list[str]):
    from PySide6.QtCore import QTimer
    from PySide6.QtDBus import QDBusConnection, QDBusInterface
    from PySide6.QtWidgets import QApplication

    from timetrace import paths, theme
    from timetrace.backends.idle_factory import select_idle_backend
    from timetrace.backends.window_factory import select_window_backend
    from timetrace.config import load_config
    from timetrace.db import Store
    from timetrace.env_detect import detect_desktop_environment, detect_session_type
    from timetrace.tracking.coordinator import TrackingCoordinator
    from timetrace.ui.main_window import MainWindow
    from timetrace.ui.settings_dialog import SettingsDialog
    from timetrace.ui.tray import TrayIcon

    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)

    bus = QDBusConnection.sessionBus()
    is_primary_instance = bus.registerService("org.timetrace.App")
    if not is_primary_instance:
        iface = QDBusInterface("org.timetrace.App", "/App", "", bus)
        iface.call("Raise")
        return app, None, None, None, None

    config = load_config(paths.config_file_path())

    theme_watch_unsubscribe: list = [None]

    def set_theme(mode: str) -> None:
        if theme_watch_unsubscribe[0] is not None:
            theme_watch_unsubscribe[0]()
            theme_watch_unsubscribe[0] = None
        theme.apply_theme(app, mode)
        if mode == "system":
            theme_watch_unsubscribe[0] = theme.watch_system_color_scheme(
                lambda scheme: theme.apply_theme(app, "system")
            )

    set_theme(config.theme)

    store = Store(paths.db_file_path())
    tz = datetime.now().astimezone().tzinfo or timezone.utc

    desktop = detect_desktop_environment()
    session = detect_session_type()
    idle_backend = select_idle_backend(desktop, session)
    window_backend = select_window_backend(desktop, session)

    coordinator = TrackingCoordinator(
        store, idle_backend, window_backend, idle_threshold_ms=config.idle_threshold_minutes * 60_000
    )
    coordinator.start()

    window = MainWindow(store, tz=tz)

    def open_settings() -> None:
        nonlocal config
        dialog = SettingsDialog(
            config,
            config_path=paths.config_file_path(),
            on_idle_threshold_changed=coordinator.update_idle_threshold,
            on_theme_changed=set_theme,
            exec_path="timetrace",
        )
        dialog.exec()
        config = load_config(paths.config_file_path())

    window.settingsRequested.connect(open_settings)

    raise_adaptor = _make_single_instance_adaptor(
        lambda: (window.show(), window.raise_(), window.activateWindow())
    )
    bus.registerObject("/App", raise_adaptor, QDBusConnection.RegisterOption.ExportAllSlots)
    window._raise_adaptor = raise_adaptor  # keep the QObject alive

    def quit_app() -> None:
        coordinator.stop()
        store.close()
        app.quit()

    tray = TrayIcon(window, on_quit=quit_app)
    tray.show()

    event_timer = QTimer()
    event_timer.timeout.connect(coordinator.process_pending_events)
    event_timer.start(250)

    refresh_timer = QTimer()
    refresh_timer.timeout.connect(window.refresh)
    refresh_timer.start(5000)

    window._event_timer = event_timer  # keep references alive
    window._refresh_timer = refresh_timer

    return app, window, coordinator, tray, quit_app


def main(argv: Optional[list[str]] = None) -> int:
    import signal

    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--version"]:
        print(f"timetrace {__version__}")
        return 0

    app, window, coordinator, tray, quit_app = build_app(sys.argv[:1] + argv)
    if window is None:
        return 0  # another instance is already running and was asked to raise its window

    # SIGTERM/SIGINT are the standard way to stop a background GUI app without
    # UI access (logout, systemd stop, `kill`, Ctrl+C) -- without a handler,
    # Python's default action just terminates the process, skipping quit_app's
    # cleanup (coordinator.stop() -> backend teardown, e.g. the KWin script
    # backend unloading its script; store.close()). Calling straight into
    # quit_app() here is the standard pragmatic PySide6/Qt pattern for a
    # quit-once-on-shutdown path; Python only runs the handler once control
    # returns to the interpreter, which happens on every 250ms event_timer
    # tick, so delivery latency is bounded by that.
    signal.signal(signal.SIGTERM, lambda *_: quit_app())
    signal.signal(signal.SIGINT, lambda *_: quit_app())

    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
