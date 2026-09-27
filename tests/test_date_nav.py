# tests/test_date_nav.py
from datetime import date, timedelta

from timetrace.ui.date_nav import DateNavigationState


def fixed_today():
    return date(2026, 9, 27)


def test_starts_at_given_date():
    state = DateNavigationState(date(2026, 9, 20), today_provider=fixed_today)
    assert state.selected == date(2026, 9, 20)


def test_go_previous_and_next():
    state = DateNavigationState(date(2026, 9, 20), today_provider=fixed_today)
    state.go_previous()
    assert state.selected == date(2026, 9, 19)
    state.go_next()
    assert state.selected == date(2026, 9, 20)


def test_go_today_jumps_to_today():
    state = DateNavigationState(date(2026, 9, 1), today_provider=fixed_today)
    state.go_today()
    assert state.selected == fixed_today()


def test_can_go_forward_false_on_today():
    state = DateNavigationState(fixed_today(), today_provider=fixed_today)
    assert state.can_go_forward is False


def test_can_go_forward_true_before_today():
    state = DateNavigationState(fixed_today() - timedelta(days=1), today_provider=fixed_today)
    assert state.can_go_forward is True


def test_go_next_is_noop_when_already_today():
    state = DateNavigationState(fixed_today(), today_provider=fixed_today)
    state.go_next()
    assert state.selected == fixed_today()
