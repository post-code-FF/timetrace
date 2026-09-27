from timetrace.backends.idle_kde_wayland import WaylandExtIdleNotifyBackend


class FakeExtIdleClient:
    def __init__(self):
        self.notifications = {}
        self._next_handle = 1

    def get_notification(self, timeout_ms, on_idled, on_resumed):
        handle = self._next_handle
        self._next_handle += 1
        self.notifications[handle] = (timeout_ms, on_idled, on_resumed)
        return handle

    def destroy_notification(self, handle):
        self.notifications.pop(handle, None)

    def stop(self):
        self.notifications.clear()

    def fire_idled(self, handle):
        self.notifications[handle][1]()

    def fire_resumed(self, handle):
        self.notifications[handle][2]()


def test_start_requests_notification_with_threshold():
    client = FakeExtIdleClient()
    backend = WaylandExtIdleNotifyBackend(client=client)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    handle = next(iter(client.notifications))
    assert client.notifications[handle][0] == 5000


def test_idled_and_resumed_events_propagate():
    client = FakeExtIdleClient()
    events = []
    backend = WaylandExtIdleNotifyBackend(client=client)
    backend.start(
        threshold_ms=5000,
        on_idle=lambda ts: events.append("idle"),
        on_resume=lambda ts: events.append("resume"),
    )
    handle = next(iter(client.notifications))
    client.fire_idled(handle)
    client.fire_resumed(handle)
    assert events == ["idle", "resume"]


def test_update_threshold_recreates_notification():
    client = FakeExtIdleClient()
    backend = WaylandExtIdleNotifyBackend(client=client)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    backend.update_threshold(9000)
    assert len(client.notifications) == 1
    assert list(client.notifications.values())[0][0] == 9000


def test_stop_destroys_notification():
    client = FakeExtIdleClient()
    backend = WaylandExtIdleNotifyBackend(client=client)
    backend.start(threshold_ms=5000, on_idle=lambda ts: None, on_resume=lambda ts: None)
    backend.stop()
    assert client.notifications == {}
