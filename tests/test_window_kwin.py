# tests/test_window_kwin.py
from timetrace.backends.window_kwin import KWinScriptActiveWindowBackend


class FakeDBusService:
    def __init__(self):
        self.on_report = None
        self.registered = False
        self.unregistered = False

    def register(self, on_report):
        self.on_report = on_report
        self.registered = True

    def unregister(self):
        self.unregistered = True


class FakeScriptLoader:
    def __init__(self):
        self.loaded_paths = []
        self.unloaded_ids = []

    def load_and_start(self, script_path):
        self.loaded_paths.append(script_path)
        return 42

    def unload(self, script_id):
        self.unloaded_ids.append(script_id)


def test_start_loads_script_and_registers_dbus_service():
    service = FakeDBusService()
    loader = FakeScriptLoader()
    backend = KWinScriptActiveWindowBackend(dbus_service=service, script_loader=loader)
    backend.start(lambda rc, title, ts: None)
    assert service.registered is True
    assert len(loader.loaded_paths) == 1
    assert loader.loaded_paths[0].endswith("main.js")


def test_dbus_report_triggers_callback_with_timestamp():
    service = FakeDBusService()
    loader = FakeScriptLoader()
    events = []
    backend = KWinScriptActiveWindowBackend(dbus_service=service, script_loader=loader)
    backend.start(lambda rc, title, ts: events.append((rc, title, ts)))

    service.on_report("firefox", "Mozilla Firefox", 1234)

    assert len(events) == 1
    assert events[0][0] == "firefox"
    assert events[0][1] == "Mozilla Firefox"
    assert isinstance(events[0][2], int)


def test_stop_unloads_script_and_unregisters_service():
    service = FakeDBusService()
    loader = FakeScriptLoader()
    backend = KWinScriptActiveWindowBackend(dbus_service=service, script_loader=loader)
    backend.start(lambda rc, title, ts: None)
    backend.stop()
    assert loader.unloaded_ids == [42]
    assert service.unregistered is True


def test_fullscreen_reports_include_same_window_toggles_and_focus_loss():
    service, loader = FakeDBusService(), FakeScriptLoader()
    backend = KWinScriptActiveWindowBackend(service, loader)
    events, windows = [], []
    backend.start_fullscreen_monitor(lambda *args: events.append(args))
    backend.start(lambda *args: windows.append(args))
    service.on_report('firefox', 'YouTube', 1234, False)
    service.on_report('firefox', 'YouTube', 1234, True)
    service.on_report('', '', 0, False)
    assert [e[0] for e in events] == [False, True, False]
    assert [w[0] for w in windows] == ['firefox', 'firefox', '']
