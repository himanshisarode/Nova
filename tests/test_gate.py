"""Phase 10: the 6-month gate (spec.md Feature 19) — each condition alone."""
from datetime import date, timedelta

import gate

TODAY = date(2026, 10, 30)


def days_back(*offsets: int) -> list[date]:
    return [TODAY - timedelta(days=k) for k in offsets]


def every_day_back_to(n: int) -> list[date]:
    return days_back(*range(n + 1))  # today ... n days ago


def conditions(status):
    return {c.label: c.met for c in status.conditions}


def test_all_three_met_opens_the_gate():
    status = gate.gate_status(every_day_back_to(180), completed_cycles=4, today=TODAY)
    assert status.open


def test_first_log_179_days_ago_is_not_enough():
    # 179 days of logging, every day logged, plenty of cycles: still closed.
    status = gate.gate_status(every_day_back_to(179), completed_cycles=6, today=TODAY)
    assert not status.open
    assert conditions(status) == {
        "days since your first log": False, "completed cycles": True,
        "days logged in the last 180": True,
    }


def test_three_completed_cycles_is_not_enough():
    status = gate.gate_status(every_day_back_to(200), completed_cycles=3, today=TODAY)
    assert not status.open and not conditions(status)["completed cycles"]
    assert gate.gate_status(every_day_back_to(200), 4, TODAY).open


def test_logging_density_boundary_89_vs_90_days():
    # First log 300 days ago (old enough), then exactly N days inside the
    # last 180 (today − 179 … today).
    old = days_back(300)
    eighty_nine = old + days_back(*range(0, 178, 2))[:89]
    ninety = old + days_back(*range(0, 180, 2))[:90]
    assert len(set(eighty_nine)) == 90 and len(set(ninety)) == 91
    assert not gate.gate_status(eighty_nine, 5, TODAY).open
    assert gate.gate_status(ninety, 5, TODAY).open


def test_a_log_180_days_ago_is_outside_the_density_window():
    # The window is the last 180 days *including today*: today − 179 … today.
    status = gate.gate_status(days_back(180), 5, TODAY)
    density = [c for c in status.conditions if c.label == "days logged in the last 180"][0]
    assert density.have == 0


def test_future_dates_dont_count_and_no_logs_is_closed():
    assert not gate.gate_status([], 0, TODAY).open
    status = gate.gate_status([TODAY + timedelta(days=5)], 0, TODAY)
    assert all(c.have == 0 for c in status.conditions if c.label != "completed cycles")


def test_thresholds_are_the_spec_values():
    assert (gate.GATE_DAYS, gate.GATE_MIN_CYCLES, gate.GATE_MIN_LOGGED_DAYS) == (180, 4, 90)
