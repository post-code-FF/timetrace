# src/timetrace/backends/window_kwin.py
import time
from importlib import resources
from typing import Callable, Protocol

from PySide6.QtCore import ClassInfo, QObject, Slot
from PySide6.QtDBus import QDBusAbstractAdaptor


class KWinScriptLoader(Protocol):
    def load_and_start(self, script_path: str) -> int: ...
    def unload(self, script_id: int) -> None: ...


_KWIN_SCRIPT_PLUGIN_NAME = "timetrace-active-window"


class QtKWinScriptLoader:
    """Real loader over org.kde.kwin.Scripting via QtDBus.

    NOTE on two real bugs found and fixed here during live verification
    against a real KDE Wayland session bus (see task-12-report.md):

    1. A loaded script's own D-Bus object lives at
       "/Scripting/Script<id>", not "/<id>". Calling run()/stop() against
       "/<id>" hits org.freedesktop.DBus.Error.UnknownObject and silently
       does nothing (QDBusInterface.call() returns an error reply, it does
       not raise) -- confirmed with `busctl --user tree org.kde.KWin`,
       which shows child objects named "Script0", "Script1", etc. under
       "/Scripting".
    2. org.kde.kwin.Scripting.unloadScript(pluginName) takes the script's
       *plugin name*, not its numeric id. loadScript(filePath) alone
       (single-arg overload) does NOT associate the file with the
       metadata.json "KPlugin.Id" -- isScriptLoaded(<that id>) returns
       false right after loading. Only the two-arg overload
       loadScript(filePath, pluginName) registers it under a name that
       isScriptLoaded()/unloadScript() can later find. Without this fix,
       every loadScript() call leaks a running script instance that
       unloadScript() can never remove (confirmed live: four such leaked
       "Script0".."Script3" objects accumulated during manual testing and
       had to be cleaned up individually via their own .stop() method).
    """

    def __init__(self) -> None:
        from PySide6.QtDBus import QDBusConnection, QDBusInterface

        bus = QDBusConnection.sessionBus()
        self._iface = QDBusInterface(
            "org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", bus
        )

    def load_and_start(self, script_path: str) -> int:
        from PySide6.QtDBus import QDBusInterface

        reply = self._iface.call("loadScript", script_path, _KWIN_SCRIPT_PLUGIN_NAME)
        script_id = int(reply.arguments()[0])
        script_iface_path = f"/Scripting/Script{script_id}"

        bus = self._iface.connection()
        script_iface = QDBusInterface("org.kde.KWin", script_iface_path, "org.kde.kwin.Script", bus)
        script_iface.call("run")
        return script_id

    def unload(self, script_id: int) -> None:
        self._iface.call("unloadScript", _KWIN_SCRIPT_PLUGIN_NAME)


class TimeTraceDBusService(Protocol):
    def register(self, on_report: Callable[[str, str, int], None]) -> None: ...
    def unregister(self) -> None: ...


@ClassInfo(**{"D-Bus Interface": "org.timetrace.ActiveWindow"})
class _TimeTraceDBusAdaptor(QDBusAbstractAdaptor):
    """QDBusAbstractAdaptor exposing ReportActiveWindow on the
    org.timetrace.ActiveWindow D-Bus interface.

    NOTE (found during live QtDBus verification on a real KDE Wayland
    session bus, see task-12-report.md): registering a *plain* QObject
    with QDBusConnection.RegisterOption.ExportAllSlots does NOT expose the
    slot under the interface name you'd expect. Qt instead synthesizes an
    interface name like "local.py.<module>.<ClassName>" from the object's
    Python module/class, so a caller targeting "org.timetrace.ActiveWindow"
    (as the bundled KWin script's callDBus() does) gets no such interface
    and the call silently fails. Subclassing QDBusAbstractAdaptor and
    attaching an explicit @ClassInfo("D-Bus Interface", ...) is what
    actually produces the "org.timetrace.ActiveWindow" interface, and the
    parent QObject must then be registered with ExportAdaptors (not
    ExportAllSlots). This was confirmed against the real session bus with
    qdbus introspection and a live ReportActiveWindow call.
    """

    def __init__(self, parent: QObject, on_report: Callable[[str, str, int], None]) -> None:
        super().__init__(parent)
        self._on_report = on_report

    @Slot(str, str, int)
    def ReportActiveWindow(self, resource_class: str, title: str, pid: int) -> None:
        self._on_report(resource_class, title, pid)


class QtTimeTraceDBusService:
    """Registers org.timetrace.App on the session bus and exposes
    /ActiveWindow org.timetrace.ActiveWindow.ReportActiveWindow(ss i)."""

    def __init__(self) -> None:
        from PySide6.QtDBus import QDBusConnection

        self._bus = QDBusConnection.sessionBus()
        self._target: QObject | None = None
        self._adaptor: _TimeTraceDBusAdaptor | None = None

    def register(self, on_report: Callable[[str, str, int], None]) -> None:
        from PySide6.QtDBus import QDBusConnection

        self._target = QObject()
        self._adaptor = _TimeTraceDBusAdaptor(self._target, on_report)
        self._bus.registerService("org.timetrace.App")
        self._bus.registerObject(
            "/ActiveWindow", self._target, QDBusConnection.RegisterOption.ExportAdaptors
        )

    def unregister(self) -> None:
        self._bus.unregisterObject("/ActiveWindow")
        self._bus.unregisterService("org.timetrace.App")
        self._adaptor = None
        self._target = None


def _bundled_script_path() -> str:
    return str(
        resources.files("timetrace.assets.kwin_script.contents.code") / "main.js"
    )


class KWinScriptActiveWindowBackend:
    def __init__(
        self,
        dbus_service: TimeTraceDBusService | None = None,
        script_loader: KWinScriptLoader | None = None,
    ) -> None:
        self._service = dbus_service or QtTimeTraceDBusService()
        self._loader = script_loader or QtKWinScriptLoader()
        self._script_id: int | None = None

    def start(self, on_window_changed: Callable[[str, str | None, int], None]) -> None:
        def on_report(resource_class: str, title: str, pid: int) -> None:
            on_window_changed(resource_class, title or None, int(time.time() * 1000))

        self._service.register(on_report)
        self._script_id = self._loader.load_and_start(_bundled_script_path())

    def stop(self) -> None:
        if self._script_id is not None:
            self._loader.unload(self._script_id)
            self._script_id = None
        self._service.unregister()
