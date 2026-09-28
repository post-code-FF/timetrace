from timetrace.backends.idle_gnome import MutterIdleMonitorBackend, QtMutterIdleDBusConnector


class FakeConnector:
    def __init__(self):
        self.idle_watches: dict[int, tuple[int, object]] = {}
        self.active_watches: dict[int, object] = {}
        self._next_id = 1

    def add_idle_watch(self, ms, callback):
        watch_id = self._next_id
        self._next_id += 1
        self.idle_watches[watch_id] = (ms, callback)
        return watch_id

    def add_active_watch(self, callback):
        watch_id = self._next_id
        self._next_id += 1
        self.active_watches[watch_id] = callback
        return watch_id

    def remove_watch(self, watch_id):
        self.idle_watches.pop(watch_id, None)
        self.active_watches.pop(watch_id, None)

    def fire_idle(self, watch_id):
        self.idle_watches[watch_id][1]()

    def fire_active(self, watch_id):
        self.active_watches[watch_id]()


def test_start_registers_idle_watch_at_threshold():
    connector = FakeConnector()
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    assert list(connector.idle_watches.values())[0][0] == 5000


def test_idle_watch_fires_on_idle_and_registers_active_watch():
    connector = FakeConnector()
    events = []
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    idle_watch_id = next(iter(connector.idle_watches))
    connector.fire_idle(idle_watch_id)
    assert events == ["idle"]
    assert len(connector.active_watches) == 1  # armed to detect resume


def test_active_watch_fires_on_resume_and_rearms_idle_watch():
    connector = FakeConnector()
    events = []
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    idle_watch_id = next(iter(connector.idle_watches))
    connector.fire_idle(idle_watch_id)
    active_watch_id = next(iter(connector.active_watches))
    connector.fire_active(active_watch_id)
    assert events == ["idle", "resume"]
    assert len(connector.idle_watches) == 1  # re-armed for next idle period


def test_update_threshold_removes_old_watch_and_adds_new_one():
    connector = FakeConnector()
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    backend.update_threshold(9000)
    assert len(connector.idle_watches) == 1
    assert list(connector.idle_watches.values())[0][0] == 9000


def test_update_threshold_while_idle_does_not_leak_a_watch():
    connector = FakeConnector()
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    idle_watch_id = next(iter(connector.idle_watches))
    connector.fire_idle(idle_watch_id)  # now idle, active watch outstanding

    backend.update_threshold(9000)  # must not arm a second idle watch

    assert connector.idle_watches == {}  # no idle watch should exist while idle
    assert len(connector.active_watches) == 1  # only the original active watch


def test_stop_removes_all_watches():
    connector = FakeConnector()
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    backend.stop()
    assert connector.idle_watches == {}


class FlakyConnector(FakeConnector):
    """A connector whose add_idle_watch fails starting from its Nth call,
    simulating a D-Bus call failing on the re-arm path (outside start())."""

    def __init__(self, fail_from_call: int):
        super().__init__()
        self._fail_from_call = fail_from_call
        self._calls = 0

    def add_idle_watch(self, ms, callback):
        self._calls += 1
        if self._calls >= self._fail_from_call:
            raise RuntimeError("org.gnome.Mutter.IdleMonitor unreachable")
        return super().add_idle_watch(ms, callback)


def test_rearm_failure_after_resume_does_not_raise():
    connector = FlakyConnector(fail_from_call=2)  # 1st call is start()'s initial arm
    events = []
    backend = MutterIdleMonitorBackend(dbus_connector=connector)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    idle_watch_id = next(iter(connector.idle_watches))
    connector.fire_idle(idle_watch_id)
    active_watch_id = next(iter(connector.active_watches))

    connector.fire_active(active_watch_id)  # triggers _handle_resume -> _arm_idle_watch (fails)

    assert events == ["idle", "resume"]  # on_resume still fired despite the failed re-arm
    assert backend._idle_watch_id is None  # degraded: no idle watch armed anymore


class FakeCompletedProcess:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_call_raises_clear_error_on_nonzero_exit(monkeypatch):
    import subprocess

    monkeypatch.setattr(
        subprocess, "run",
        lambda *a, **k: FakeCompletedProcess(1, stderr="GDBus.Error:...ServiceUnknown"),
    )
    connector = QtMutterIdleDBusConnector.__new__(QtMutterIdleDBusConnector)
    try:
        connector._call("AddIdleWatch", "uint64 5000")
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "AddIdleWatch" in str(exc)
        assert "ServiceUnknown" in str(exc)
    assert raised


def test_call_returns_stdout_on_success(monkeypatch):
    import subprocess

    monkeypatch.setattr(subprocess, "run", lambda *a, **k: FakeCompletedProcess(0, stdout="(5,)\n"))
    connector = QtMutterIdleDBusConnector.__new__(QtMutterIdleDBusConnector)
    assert connector._call("AddIdleWatch", "uint64 5000") == "(5,)"


def test_call_passes_explicitly_typed_gvariant_arguments(monkeypatch):
    import subprocess

    captured = {}

    def fake_run(argv, **kwargs):
        captured["argv"] = argv
        return FakeCompletedProcess(0, stdout="(5,)\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    connector = QtMutterIdleDBusConnector.__new__(QtMutterIdleDBusConnector)
    connector._call("AddIdleWatch", "uint64 5000")
    # Must be an explicit GVariant-typed literal (e.g. "uint64 5000"), not a
    # bare number -- a bare int would be ambiguous and mismarshal, which is
    # exactly the bug this connector works around (see class docstring).
    assert "uint64 5000" in captured["argv"]


def test_parse_reply_uint_extracts_id_from_gvariant_tuple():
    assert QtMutterIdleDBusConnector._parse_reply_uint("(5,)", "AddIdleWatch") == 5


def test_parse_reply_uint_raises_on_unexpected_output():
    try:
        QtMutterIdleDBusConnector._parse_reply_uint("garbage", "AddIdleWatch")
        raised = False
    except RuntimeError as exc:
        raised = True
        assert "AddIdleWatch" in str(exc)
    assert raised
