from timetrace.backends.window_gnome import GnomeShellExtensionBackend


class FakeInstaller:
    def __init__(self, enabled_immediately=True):
        self._enabled_immediately = enabled_immediately
        self.install_called = False

    def install_and_enable(self):
        self.install_called = True
        return self._enabled_immediately


class FakeDBusClient:
    def __init__(self):
        self.callback = None
        self.unsubscribed = False

    def subscribe_active_window_changed(self, callback):
        self.callback = callback

    def unsubscribe(self):
        self.unsubscribed = True


def test_start_installs_extension_and_subscribes():
    installer = FakeInstaller()
    client = FakeDBusClient()
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: None)
    assert installer.install_called is True
    assert client.callback is not None


def test_start_does_not_raise_when_extension_needs_relogin():
    installer = FakeInstaller(enabled_immediately=False)
    client = FakeDBusClient()
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: None)  # must not raise
    assert backend.needs_relogin is True


def test_signal_triggers_callback_with_timestamp():
    installer = FakeInstaller()
    client = FakeDBusClient()
    events = []
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: events.append((rc, title, ts)))
    client.callback("firefox", "Mozilla Firefox")
    assert len(events) == 1
    assert events[0][0] == "firefox"
    assert isinstance(events[0][2], int)


def test_stop_unsubscribes():
    installer = FakeInstaller()
    client = FakeDBusClient()
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: None)
    backend.stop()
    assert client.unsubscribed is True
