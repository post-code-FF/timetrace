# tests/test_idle_state_machine.py
from timetrace.backends.idle_state_machine import IdleStateMachine


def test_starts_active_and_stays_active_below_threshold():
    m = IdleStateMachine(threshold_ms=5000)
    assert m.feed(idle_ms=1000, now_ts=1000) == "none"
    assert m.feed(idle_ms=4000, now_ts=4000) == "none"


def test_fires_idled_once_when_crossing_threshold():
    m = IdleStateMachine(threshold_ms=5000)
    m.feed(idle_ms=1000, now_ts=1000)
    assert m.feed(idle_ms=5000, now_ts=5000) == "idled"
    assert m.feed(idle_ms=6000, now_ts=6000) == "none"  # already idle, no repeat


def test_fires_resumed_once_when_idle_ms_drops():
    m = IdleStateMachine(threshold_ms=5000)
    m.feed(idle_ms=5000, now_ts=5000)  # idled
    assert m.feed(idle_ms=0, now_ts=6000) == "resumed"
    assert m.feed(idle_ms=100, now_ts=6100) == "none"  # already active


def test_update_threshold_does_not_fire_spurious_event_mid_flight():
    m = IdleStateMachine(threshold_ms=5000)
    m.feed(idle_ms=2000, now_ts=2000)  # still active, 2s idle so far
    m.update_threshold(10000)  # user raises threshold to 10 minutes... err 10s
    # same idle duration as before the change must not trip anything by itself
    assert m.feed(idle_ms=2000, now_ts=2000) == "none"
    assert m.feed(idle_ms=9000, now_ts=9000) == "none"  # below new threshold
    assert m.feed(idle_ms=10000, now_ts=10000) == "idled"  # crosses new threshold


def test_lowering_threshold_below_current_idle_time_fires_idled_on_next_feed():
    m = IdleStateMachine(threshold_ms=10000)
    m.feed(idle_ms=6000, now_ts=6000)  # active, below 10s threshold
    m.update_threshold(5000)  # lower threshold to 5s; already-elapsed 6s now qualifies
    assert m.feed(idle_ms=6000, now_ts=6000) == "idled"
