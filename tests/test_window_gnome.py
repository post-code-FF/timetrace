from timetrace.backends import window_gnome
from timetrace.backends.window_gnome import GnomeShellExtensionBackend, RealGnomeExtensionInstaller


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


def test_install_and_enable_returns_false_when_gnome_extensions_missing(tmp_path, monkeypatch):
    def raise_missing_binary(*args, **kwargs):
        raise FileNotFoundError("gnome-extensions not found")

    monkeypatch.setattr(window_gnome.subprocess, "run", raise_missing_binary)
    installer = RealGnomeExtensionInstaller(extensions_dir=tmp_path)

    assert installer.install_and_enable() is False  # must not raise


def test_install_and_enable_passes_system_subprocess_env(tmp_path, monkeypatch):
    captured = {}

    def fake_run(argv, **kwargs):
        captured["kwargs"] = kwargs

        class Result:
            returncode = 0

        return Result()

    monkeypatch.setattr(window_gnome.subprocess, "run", fake_run)
    monkeypatch.setattr(window_gnome, "system_subprocess_env", lambda: {"sentinel": "1"})
    installer = RealGnomeExtensionInstaller(extensions_dir=tmp_path)
    installer.install_and_enable()
    # gnome-extensions must not inherit the frozen app's LD_LIBRARY_PATH (see
    # subprocess_env.py / the sibling fix in idle_gnome.py's gdbus call).
    assert captured["kwargs"]["env"] == {"sentinel": "1"}


def test_stop_unsubscribes():
    installer = FakeInstaller()
    client = FakeDBusClient()
    backend = GnomeShellExtensionBackend(extension_installer=installer, dbus_client=client)
    backend.start(lambda rc, title, ts: None)
    backend.stop()
    assert client.unsubscribed is True
