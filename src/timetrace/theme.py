# src/timetrace/theme.py
from typing import Callable, Literal

ColorScheme = Literal["light", "dark", "unknown"]

_SERVICE = "org.freedesktop.portal.Desktop"
_PATH = "/org/freedesktop/portal/desktop"
_INTERFACE = "org.freedesktop.portal.Settings"
_NAMESPACE = "org.freedesktop.appearance"
_KEY = "color-scheme"


def _unwrap_dbus_variant(value):
    """Recursively unwrap QDBusVariant to the underlying Python value.

    org.freedesktop.portal.Settings.Read replies with a variant that
    itself wraps another variant (a portal quirk to preserve type info
    generically), while the SettingChanged signal's value argument is
    only wrapped once. Unwrapping until we hit a non-variant handles
    both shapes without hardcoding a depth. Verified empirically against
    the live xdg-desktop-portal service on this machine.
    """
    from PySide6.QtDBus import QDBusVariant

    while isinstance(value, QDBusVariant):
        value = value.variant()
    return value


def _portal_value_to_abstract(portal_value: int) -> int:
    """Translate the real org.freedesktop.appearance color-scheme value
    to this module's abstract reader/subscriber contract.

    The real portal setting uses 0=no-preference, 1=prefer-dark,
    2=prefer-light. read_system_color_scheme/watch_system_color_scheme
    (and their tests) use a different, simpler convention via the
    injected reader/subscriber: 0="light", 1="dark", anything else
    ="unknown". Without this translation, a real light preference
    (portal 2) would incorrectly report "unknown", and no-preference
    (portal 0, a common default) would incorrectly report "light" with
    false confidence. This mapping is applied only in the real (non-test)
    D-Bus code paths -- the abstract contract and its 5 tests are
    untouched.
    """
    return {1: 1, 2: 0}.get(portal_value, -1)


def _real_reader() -> int:
    from PySide6.QtDBus import QDBusInterface

    iface = QDBusInterface(_SERVICE, _PATH, _INTERFACE)
    reply = iface.call("Read", _NAMESPACE, _KEY)
    portal_value = int(_unwrap_dbus_variant(reply.arguments()[0]))
    return _portal_value_to_abstract(portal_value)


def read_system_color_scheme(reader: Callable[[], int] | None = None) -> ColorScheme:
    reader = reader or _real_reader
    try:
        value = reader()
    except Exception:
        return "unknown"
    return {0: "light", 1: "dark"}.get(value, "unknown")


def _real_subscriber(handler: Callable[[int], None]) -> Callable[[], None]:
    from PySide6.QtCore import QObject, SLOT, Slot
    from PySide6.QtDBus import QDBusConnection

    bus = QDBusConnection.sessionBus()

    # QDBusConnection.connect() requires a QObject receiver plus a Qt slot
    # signature (built via SLOT()) -- a plain Python callable is not an
    # accepted overload for receiving a D-Bus signal. Route the signal to
    # a tiny QObject whose @Slot-decorated method forwards to our real
    # handler, the same pattern used by QtMutterIdleDBusConnector in
    # idle_gnome.py and QtActiveWindowDBusClient in window_gnome.py.
    # SettingChanged's signature is "ssv" (namespace, key, variant value);
    # the variant argument maps to Qt's QDBusVariant type.
    class _SettingChangedReceiver(QObject):
        @Slot(str, str, "QDBusVariant")
        def on_setting_changed(self, namespace: str, key: str, value) -> None:
            if namespace == _NAMESPACE and key == _KEY:
                portal_value = int(_unwrap_dbus_variant(value))
                handler(_portal_value_to_abstract(portal_value))

    receiver = _SettingChangedReceiver()
    bus.connect(
        _SERVICE, _PATH, _INTERFACE, "SettingChanged",
        receiver, SLOT("on_setting_changed(QString,QString,QDBusVariant)"),
    )

    def unsubscribe() -> None:
        bus.disconnect(
            _SERVICE, _PATH, _INTERFACE, "SettingChanged",
            receiver, SLOT("on_setting_changed(QString,QString,QDBusVariant)"),
        )

    return unsubscribe


def watch_system_color_scheme(
    on_change: Callable[[Literal["light", "dark"]], None],
    subscriber: Callable[[Callable[[int], None]], Callable[[], None]] | None = None,
) -> Callable[[], None]:
    subscriber = subscriber or _real_subscriber

    def handler(value: int) -> None:
        scheme = {0: "light", 1: "dark"}.get(value)
        if scheme is not None:
            on_change(scheme)

    return subscriber(handler)


# Палитры задают КАЖДУЮ роль явно. Если оставить часть ролей незаданной, Qt
# подставит их из палитры платформы (в KDE -- из kdeglobals), и на тёмной
# схеме ОС «светлая» тема остаётся тёмной, а «тёмная» почти не отличается.
_PALETTES: dict[str, dict[str, tuple[int, ...]]] = {
    "light": {
        "Window": (239, 239, 239), "WindowText": (0, 0, 0),
        "Base": (255, 255, 255), "AlternateBase": (247, 247, 247),
        "ToolTipBase": (255, 255, 220), "ToolTipText": (0, 0, 0),
        "Text": (0, 0, 0), "Button": (239, 239, 239), "ButtonText": (0, 0, 0),
        "BrightText": (255, 255, 255), "Highlight": (48, 140, 198),
        "HighlightedText": (255, 255, 255), "Link": (0, 0, 255),
        "LinkVisited": (255, 0, 255), "PlaceholderText": (0, 0, 0, 128),
        "Light": (255, 255, 255), "Midlight": (227, 227, 227),
        "Mid": (160, 160, 160), "Dark": (120, 120, 120), "Shadow": (0, 0, 0),
        "Disabled": (140, 140, 140),
    },
    "dark": {
        "Window": (45, 45, 45), "WindowText": (230, 230, 230),
        "Base": (30, 30, 30), "AlternateBase": (38, 38, 38),
        "ToolTipBase": (60, 60, 60), "ToolTipText": (230, 230, 230),
        "Text": (230, 230, 230), "Button": (53, 53, 53), "ButtonText": (230, 230, 230),
        "BrightText": (255, 255, 255), "Highlight": (42, 130, 218),
        "HighlightedText": (255, 255, 255), "Link": (90, 170, 255),
        "LinkVisited": (180, 130, 230), "PlaceholderText": (230, 230, 230, 128),
        "Light": (80, 80, 80), "Midlight": (66, 66, 66),
        "Mid": (38, 38, 38), "Dark": (25, 25, 25), "Shadow": (15, 15, 15),
        "Disabled": (127, 127, 127),
    },
}


def _build_palette(scheme: str):
    from PySide6.QtGui import QColor, QPalette

    colors = dict(_PALETTES[scheme])
    disabled = QColor(*colors.pop("Disabled"))
    palette = QPalette()
    for role_name, rgba in colors.items():
        palette.setColor(getattr(QPalette, role_name), QColor(*rgba))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, disabled)
    return palette


def apply_theme(app, mode: Literal["light", "dark", "system"]) -> None:
    from PySide6.QtGui import QPalette

    # Запоминаем палитру, с которой стартовала ОС, до первого вмешательства.
    if not hasattr(app, "_timetrace_os_palette"):
        app._timetrace_os_palette = QPalette(app.palette())

    effective = mode
    if mode == "system":
        detected = read_system_color_scheme()
        if detected not in ("light", "dark"):
            # Портал недоступен -- не гадаем: оставляем как у ОС.
            app.setPalette(QPalette(app._timetrace_os_palette))
            return
        effective = detected

    app.setPalette(_build_palette(effective))
