from timetrace.backends.sleep_monitor import NullSleepMonitor, SleepMonitor


class FakeConnector:
    def __init__(self):
        self.callback = None
        self.unsubscribed = False

    def subscribe_prepare_for_sleep(self, callback):
        self.callback = callback

    def unsubscribe(self):
        self.unsubscribed = True


def test_start_subscribes_to_prepare_for_sleep():
    connector = FakeConnector()
    monitor = SleepMonitor(connector=connector)
    monitor.start(on_sleep=lambda ts: None, on_wake=lambda ts: None)
    assert connector.callback is not None


def test_prepare_for_sleep_true_triggers_on_sleep():
    connector = FakeConnector()
    events = []
    monitor = SleepMonitor(connector=connector)
    monitor.start(on_sleep=lambda ts: events.append(("sleep", ts)), on_wake=lambda ts: events.append(("wake", ts)))
    connector.callback(True)
    assert len(events) == 1
    assert events[0][0] == "sleep"
    assert isinstance(events[0][1], int)


def test_prepare_for_sleep_false_triggers_on_wake():
    connector = FakeConnector()
    events = []
    monitor = SleepMonitor(connector=connector)
    monitor.start(on_sleep=lambda ts: events.append(("sleep", ts)), on_wake=lambda ts: events.append(("wake", ts)))
    connector.callback(False)
    assert events == [("wake", events[0][1])]


def test_stop_unsubscribes():
    connector = FakeConnector()
    monitor = SleepMonitor(connector=connector)
    monitor.start(on_sleep=lambda ts: None, on_wake=lambda ts: None)
    monitor.stop()
    assert connector.unsubscribed is True


def test_null_sleep_monitor_does_nothing():
    monitor = NullSleepMonitor()
    monitor.start(on_sleep=lambda ts: None, on_wake=lambda ts: None)  # must not raise
    monitor.stop()  # must not raise
