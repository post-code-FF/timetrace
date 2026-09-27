import subprocess
import time
from importlib import resources
from pathlib import Path
from typing import Callable, Protocol

EXTENSION_UUID = "timetrace@timetrace.app"


class GnomeExtensionInstaller(Protocol):
    def install_and_enable(self) -> bool: ...


class RealGnomeExtensionInstaller:
    def __init__(self, extensions_dir: Path | None = None) -> None:
        self._extensions_dir = extensions_dir or (
            Path.home() / ".local" / "share" / "gnome-shell" / "extensions"
        )

    def install_and_enable(self) -> bool:
        target = self._extensions_dir / EXTENSION_UUID
        target.mkdir(parents=True, exist_ok=True)
        src_dir = resources.files("timetrace.assets.gnome_extension")
        for name in ("metadata.json", "extension.js"):
            (target / name).write_bytes((src_dir / name).read_bytes())

        result = subprocess.run(
            ["gnome-extensions", "enable", EXTENSION_UUID],
            capture_output=True,
        )
        return result.returncode == 0


class GnomeShellExtensionDBusClient(Protocol):
    def subscribe_active_window_changed(self, callback: Callable[[str, str], None]) -> None: ...
    def unsubscribe(self) -> None: ...


class QtGnomeShellExtensionDBusClient:
    """Real client subscribing to org.timetrace.ActiveWindow.ActiveWindowChanged
    (emitted by the bundled GNOME Shell extension) via QtDBus.

    NOTE on D-Bus signal reception with QtDBus (see idle_gnome.py's
    QtMutterIdleDBusConnector for the sibling fix this mirrors, found
    during Task 9's live verification): QDBusConnection.connect() does
    NOT accept a plain Python callable as its receiver when subscribing
    to a D-Bus SIGNAL -- that overload is for something else entirely and
    silently fails to deliver the signal. The receiver must be a QObject
    instance plus a Qt slot signature built via SLOT(), i.e. the 6-arg
    overload: connect(service, path, interface, signalName,
    receiverQObject, SLOT("methodName(<types>)")). ActiveWindowChanged
    carries two D-Bus "s" (string) arguments, which map to Qt's QString,
    so the slot signature is "on_signal(QString,QString)" and the
    receiving Python method is decorated with @Slot(str, str) (PySide6
    maps `str` to QString for signal/slot purposes).
    """

    SERVICE = "org.gnome.Shell"
    PATH = "/org/timetrace/ActiveWindow"
    INTERFACE = "org.timetrace.ActiveWindow"

    def __init__(self) -> None:
        from PySide6.QtCore import QObject, SLOT, Slot
        from PySide6.QtDBus import QDBusConnection

        self._bus = QDBusConnection.sessionBus()
        self._callback: Callable[[str, str], None] | None = None

        # See class docstring: a plain Python callable is not an accepted
        # receiver for QDBusConnection.connect() when subscribing to a
        # D-Bus signal. Route the signal to a tiny QObject whose
        # @Slot-decorated method forwards to our real handler, and
        # connect via the 6-arg QObject+SLOT() overload -- the same
        # pattern used by QtMutterIdleDBusConnector in idle_gnome.py.
        outer = self

        class _ActiveWindowChangedReceiver(QObject):
            @Slot(str, str)
            def on_active_window_changed(self, resource_class: str, title: str) -> None:
                outer._on_signal(resource_class, title)

        self._receiver = _ActiveWindowChangedReceiver()

    def subscribe_active_window_changed(self, callback: Callable[[str, str], None]) -> None:
        from PySide6.QtCore import SLOT

        self._callback = callback
        self._bus.connect(
            self.SERVICE, self.PATH, self.INTERFACE, "ActiveWindowChanged",
            self._receiver, SLOT("on_active_window_changed(QString,QString)"),
        )

    def _on_signal(self, resource_class: str, title: str) -> None:
        if self._callback:
            self._callback(resource_class, title)

    def unsubscribe(self) -> None:
        from PySide6.QtCore import SLOT

        self._bus.disconnect(
            self.SERVICE, self.PATH, self.INTERFACE, "ActiveWindowChanged",
            self._receiver, SLOT("on_active_window_changed(QString,QString)"),
        )


class GnomeShellExtensionBackend:
    def __init__(
        self,
        extension_installer: GnomeExtensionInstaller | None = None,
        dbus_client: GnomeShellExtensionDBusClient | None = None,
    ) -> None:
        self._installer = extension_installer or RealGnomeExtensionInstaller()
        self._client = dbus_client or QtGnomeShellExtensionDBusClient()
        self.needs_relogin = False

    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None:
        enabled = self._installer.install_and_enable()
        self.needs_relogin = not enabled

        def on_signal(resource_class: str, title: str) -> None:
            on_window_changed(resource_class, title or None, int(time.time() * 1000))

        self._client.subscribe_active_window_changed(on_signal)

    def stop(self) -> None:
        self._client.unsubscribe()
