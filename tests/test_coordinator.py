# tests/test_coordinator.py
from timetrace.db import Store
from timetrace.tracking.coordinator import TrackingCoordinator


class FakeIdleBackend:
    def __init__(self):
        self.on_idle = None
        self.on_resume = None
        self.started_threshold_ms = None
        self.updated_threshold_ms = None
        self.stopped = False

    def start(self, threshold_ms, on_idle, on_resume):
        self.started_threshold_ms = threshold_ms
        self.on_idle = on_idle
        self.on_resume = on_resume

    def update_threshold(self, threshold_ms):
        self.updated_threshold_ms = threshold_ms

    def stop(self):
        self.stopped = True


class FakeWindowBackend:
    def __init__(self):
        self.on_window_changed = None
        self.stopped = False

    def start(self, on_window_changed):
        self.on_window_changed = on_window_changed

    def stop(self):
        self.stopped = True


def make_coordinator(tmp_path, clock_values):
    store = Store(tmp_path / "data.db")
    idle = FakeIdleBackend()
    window = FakeWindowBackend()
    clock = iter(clock_values)
    coordinator = TrackingCoordinator(
        store, idle, window, idle_threshold_ms=5000, clock=lambda: next(clock)
    )
    return store, idle, window, coordinator


def test_start_opens_active_presence_interval_and_arms_backends(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000])
    coordinator.start()

    assert idle.started_threshold_ms == 5000
    assert window.on_window_changed is not None
    open_interval = store.get_open_presence_interval()
    assert open_interval is not None
    assert open_interval.state == "active"
    assert open_interval.start_ts == 1000
    store.close()


def test_window_change_while_active_opens_app_interval(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()

    open_app = store.get_open_app_interval()
    assert open_app is not None
    assert open_app.resource_class == "firefox"
    assert open_app.start_ts == 2000
    store.close()


def test_repeated_same_window_event_does_not_churn_db(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 3000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()
    first_open = store.get_open_app_interval()

    window.on_window_changed("firefox", "Mozilla Firefox — tab 2", 3000)
    coordinator.process_pending_events()
    second_open = store.get_open_app_interval()

    assert second_open.id == first_open.id  # same interval, not a new row
    assert second_open.start_ts == first_open.start_ts
    store.close()


def test_switching_window_closes_old_app_interval_and_opens_new_one(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 3000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()
    window.on_window_changed("code", "VS Code", 3000)
    coordinator.process_pending_events()

    open_app = store.get_open_app_interval()
    assert open_app.resource_class == "code"
    assert open_app.start_ts == 3000

    day_rows = store.app_intervals_for_day(0, 10_000, now_ts=3000)
    firefox_rows = [r for r in day_rows if r.resource_class == "firefox"]
    assert len(firefox_rows) == 1
    assert firefox_rows[0].end_ts == 3000
    store.close()


def test_idle_closes_presence_and_app_intervals(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 6000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()

    idle.on_idle(6000)
    coordinator.process_pending_events()

    assert store.get_open_app_interval() is None
    presence = store.get_open_presence_interval()
    assert presence.state == "idle"
    assert presence.start_ts == 6000
    store.close()


def test_resume_reopens_app_interval_for_last_known_window_without_new_event(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 6000, 9000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()
    idle.on_idle(6000)
    coordinator.process_pending_events()

    idle.on_resume(9000)
    coordinator.process_pending_events()

    presence = store.get_open_presence_interval()
    assert presence.state == "active"
    assert presence.start_ts == 9000

    open_app = store.get_open_app_interval()
    assert open_app is not None
    assert open_app.resource_class == "firefox"
    assert open_app.start_ts == 9000
    store.close()


def test_window_event_while_idle_is_remembered_but_not_written(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 6000, 7000, 9000])
    coordinator.start()
    idle.on_idle(6000)
    coordinator.process_pending_events()

    window.on_window_changed("code", "VS Code", 7000)  # focus-steal while idle
    coordinator.process_pending_events()
    assert store.get_open_app_interval() is None  # not written while idle

    idle.on_resume(9000)
    coordinator.process_pending_events()
    open_app = store.get_open_app_interval()
    assert open_app.resource_class == "code"  # remembered window is used on resume
    assert open_app.start_ts == 9000
    store.close()


def test_update_idle_threshold_forwards_minutes_as_ms(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000])
    coordinator.start()
    coordinator.update_idle_threshold(10)
    assert idle.updated_threshold_ms == 600_000
    store.close()


def test_stop_stops_backends_and_closes_open_intervals(tmp_path):
    store, idle, window, coordinator = make_coordinator(tmp_path, [1000, 2000, 5000])
    coordinator.start()
    window.on_window_changed("firefox", "Mozilla Firefox", 2000)
    coordinator.process_pending_events()

    coordinator.stop()

    assert idle.stopped is True
    assert window.stopped is True
    assert store.get_open_presence_interval() is None
    assert store.get_open_app_interval() is None
    store.close()


def test_start_reconciles_stale_open_intervals_from_previous_run(tmp_path):
    db_path = tmp_path / "data.db"
    stale_store = Store(db_path)
    stale_store.open_presence_interval("active", 500)
    stale_store.open_app_interval("old-app", None, 500)
    stale_store.close()

    store = Store(db_path)
    idle = FakeIdleBackend()
    window = FakeWindowBackend()
    coordinator = TrackingCoordinator(store, idle, window, idle_threshold_ms=5000, clock=lambda: 1000)
    coordinator.start()

    # the stale rows must be closed at startup time, and a fresh interval opened
    day_rows = store.presence_intervals_for_day(0, 10_000, now_ts=1000)
    closed_stale = [r for r in day_rows if r.start_ts == 500]
    assert len(closed_stale) == 1
    assert closed_stale[0].end_ts == 1000
    assert store.get_open_presence_interval().start_ts == 1000
    store.close()
