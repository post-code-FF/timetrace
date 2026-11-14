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


def test_real_client_sends_registration_and_uses_input_only_idle(monkeypatch):
    """The simulated compositor cannot deliver idle before the request is flushed."""
    import socket
    import pywayland.client
    from timetrace.backends.idle_kde_wayland import PywaylandExtIdleClient

    class Notification:
        def __init__(self):
            self.dispatcher = {}
        def destroy(self):
            pass

    class Display:
        def __init__(self):
            self.reader, self.writer = socket.socketpair()
            self.notifier = self
            self.dispatcher = {}
            self.pending = []
            self.input_only = False
        def connect(self):
            pass
        def get_registry(self):
            return self
        def roundtrip(self):
            self.dispatcher['global'](self, 1, 'ext_idle_notifier_v1', 2)
            self.dispatcher['global'](self, 2, 'wl_seat', 9)
        def bind(self, ident, interface, version):
            return self
        def get_fd(self):
            return self.reader.fileno()
        def get_idle_notification(self, timeout, seat):
            n = Notification()
            self.pending.append(n)
            return n
        def get_input_idle_notification(self, timeout, seat):
            self.input_only = True
            return self.get_idle_notification(timeout, seat)
        def flush(self):
            for n in self.pending:
                n.dispatcher['idled'](n)
            self.pending.clear()
            return 0
        def dispatch(self, **kwargs):
            pass
        def disconnect(self):
            self.reader.close()
            self.writer.close()

    monkeypatch.setattr(pywayland.client, 'Display', Display)
    client = PywaylandExtIdleClient()
    events = []
    try:
        client.get_notification(5000, lambda: events.append('idle'), lambda: events.append('resume'))
        assert events == ['idle']
        assert client._display.input_only
    finally:
        client.stop()
    assert not client._dispatch_thread.is_alive()


def test_changing_threshold_while_idle_starts_new_observation_period():
    client = FakeExtIdleClient()
    events = []
    backend = WaylandExtIdleNotifyBackend(client)
    backend.start(5000, lambda ts: events.append('idle'), lambda ts: events.append('resume'))
    client.fire_idled(next(iter(client.notifications)))
    backend.update_threshold(9000)
    assert events == ['idle', 'resume']
    client.fire_idled(next(iter(client.notifications)))
    assert events == ['idle', 'resume', 'idle']
    backend.stop()
