"""Phase 10: personal phase tracker (spec.md Feature 17).

Every expected date below is worked out by hand in the comments, from
the rule in the spec, not from the code.
"""
from datetime import date, timedelta

import phases


def d(month: int, day: int) -> date:
    return date(2026, month, day)


def span(a: date, b: date) -> list[date]:
    return [a + timedelta(days=k) for k in range((b - a).days + 1)]


def expect(result: dict, phase: str, a: date, b: date) -> None:
    for day in span(a, b):
        assert result[day] == phase, (day, result[day], phase)


# --- completed cycles ---------------------------------------------------------

def test_29_day_cycle_default_luteal():
    # Jan 1 → Jan 30 (29 days), bleeding Jan 1–5.
    # Ovulation = Jan 30 − 14 = Jan 16; window Jan 14–18; luteal Jan 19–29.
    result = phases.completed_cycle_phases(d(1, 1), d(1, 30), d(1, 5))
    assert len(result) == 29
    expect(result, "period", d(1, 1), d(1, 5))
    expect(result, "follicular", d(1, 6), d(1, 13))
    expect(result, "ovulation_window", d(1, 14), d(1, 18))
    expect(result, "luteal", d(1, 19), d(1, 29))


def test_luteal_setting_moves_ovulation_back_from_the_next_period():
    # Same cycle, L = 12: ovulation Jan 18; window Jan 16–20; luteal Jan 21–29.
    result = phases.completed_cycle_phases(d(1, 1), d(1, 30), d(1, 5), luteal_days=12)
    expect(result, "follicular", d(1, 6), d(1, 15))
    expect(result, "ovulation_window", d(1, 16), d(1, 20))
    expect(result, "luteal", d(1, 21), d(1, 29))


def test_24_day_cycle():
    # Mar 1 → Mar 25, bleeding Mar 1–6. Ovulation Mar 11; window Mar 9–13;
    # luteal Mar 14–24; follicular only Mar 7–8.
    result = phases.completed_cycle_phases(d(3, 1), d(3, 25), d(3, 6))
    expect(result, "period", d(3, 1), d(3, 6))
    expect(result, "follicular", d(3, 7), d(3, 8))
    expect(result, "ovulation_window", d(3, 9), d(3, 13))
    expect(result, "luteal", d(3, 14), d(3, 24))


def test_38_day_cycle_has_a_long_follicular_phase_not_a_long_luteal_one():
    # Apr 1 → May 9 (38 days), bleeding Apr 1–4. Ovulation Apr 25;
    # window Apr 23–27; luteal Apr 28–May 8 (still 11 days); follicular Apr 5–22.
    result = phases.completed_cycle_phases(d(4, 1), d(5, 9), d(4, 4))
    expect(result, "period", d(4, 1), d(4, 4))
    expect(result, "follicular", d(4, 5), d(4, 22))
    expect(result, "ovulation_window", d(4, 23), d(4, 27))
    expect(result, "luteal", d(4, 28), d(5, 8))


def test_short_cycle_overlap_period_wins_then_luteal():
    # Jun 1 → Jun 13 (12 days), bleeding Jun 1–5. Ovulation would be May 30,
    # before the cycle; luteal starts Jun 2 — but period days win.
    result = phases.completed_cycle_phases(d(6, 1), d(6, 13), d(6, 5))
    expect(result, "period", d(6, 1), d(6, 5))
    expect(result, "luteal", d(6, 6), d(6, 12))
    assert "follicular" not in result.values() and "ovulation_window" not in result.values()


def test_no_28_day_template_phases_scale_with_the_users_cycles():
    # Three 35-day cycles from Jan 1: Jan 1, Feb 5, Mar 12, Apr 16.
    starts = [d(1, 1), d(2, 5), d(3, 12), d(4, 16)]
    bleeding = [s + timedelta(days=k) for s in starts for k in range(5)]
    result = phases.history_phases(starts, bleeding)
    # In the Feb 5 cycle (next Mar 12): ovulation Feb 26 — day 22, not 14.
    assert result[d(2, 26)] == "ovulation_window"
    assert result[d(2, 18)] == "follicular"  # day 14 of the cycle
    assert d(4, 16) not in result  # the open cycle isn't included


def test_period_end_follows_the_period_rule():
    # Bleeds Jan 1, 2, then Jan 5 (gap of 2 days) — one period, ends Jan 5.
    # A bleed on Jan 20 is 15 days later: not part of this period.
    bleeding = [d(1, 1), d(1, 2), d(1, 5), d(1, 20)]
    assert phases.period_end(d(1, 1), bleeding) == d(1, 5)


def test_buckets_group_the_ovulation_window_with_follicular():
    assert phases.BUCKET_OF["ovulation_window"] == "follicular"
    assert set(phases.BUCKET_OF.values()) == set(phases.BUCKETS)


# --- current cycle --------------------------------------------------------------
# Completed cycles 28, 30, 29 days: Jan 1, Jan 29, Feb 28, then the open
# cycle from Mar 29; each period 5 days.
# Honest 90% range (worked by hand): mean 29, sd 1, n 3, t(0.95, 2) = 2.920,
# half-width = 2.920 · 1 · √(4/3) = 3.372 → 25.63..32.37 → 25..33 days
# → next start between Apr 23 (Mar 29 + 25) and May 1 (Mar 29 + 33).
# L = 14: ovulation window Apr 23 − 16 = Apr 7 … May 1 − 12 = Apr 19;
# luteal from May 1 − 11 = Apr 20.

STARTS = [d(1, 1), d(1, 29), d(2, 28), d(3, 29)]
LENGTHS = [28, 30, 29]
BLEEDING = [s + timedelta(days=k) for s in STARTS for k in range(5)]


def current(today, bleeding=BLEEDING, lengths=LENGTHS):
    return phases.current_cycle(STARTS, bleeding, lengths, today)


def test_current_cycle_windows():
    c = current(d(4, 10))
    assert (c.next_earliest, c.next_latest) == (d(4, 23), d(5, 1))
    assert (c.ovulation_from, c.ovulation_to) == (d(4, 7), d(4, 19))
    assert c.luteal_from == d(4, 20)
    assert c.ovulation_from < c.ovulation_to  # a window, never a single day
    assert c.day == 13


def test_current_phase_today():
    assert current(d(4, 5)).phase_today == "follicular"
    assert current(d(4, 10)).phase_today == "ovulation_window"
    assert current(d(4, 20)).phase_today == "luteal"
    assert current(d(3, 31)).phase_today == "period"


def test_an_ongoing_period_isnt_cut_short_by_a_missing_log():
    # Day 3 (Mar 31), only Mar 29–30 logged so far: the period is assumed
    # to run its typical 5 days (to Apr 2), so Mar 31 is still "period".
    bleeding = [x for x in BLEEDING if x < d(3, 31)]
    assert current(d(3, 31), bleeding).phase_today == "period"


def test_late_period_is_uncertain_not_a_stale_guess():
    c = current(d(5, 2))
    assert c.late and c.phase_today is None


def test_fewer_than_3_cycles_only_the_period_is_known():
    c = current(d(4, 10), lengths=[28, 30])
    assert not c.enough_data and c.phase_today is None and c.ovulation_from is None
    assert current(d(3, 30), lengths=[28, 30]).phase_today == "period"


def test_no_periods_logged_means_no_tracker():
    assert phases.current_cycle([], [], [], d(4, 10)) is None


# --- candidate buckets for coming days (Week Fit rule) ---------------------------
# Possible next starts n = Apr 23 … May 1; for each n, luteal starts n − 11
# and the window is n − 16 … n − 12.

def test_candidate_buckets():
    c = current(d(4, 10))
    cb = lambda day: phases.candidate_buckets(day, c, period_days=5)
    # Apr 21: luteal for every n (latest luteal start is Apr 20).
    assert cb(d(4, 21)) == {"luteal"}
    # Apr 16: luteal if n = Apr 23 (from Apr 12), window if n = May 1 (Apr 15–19).
    assert cb(d(4, 16)) == {"luteal", "follicular"}
    # Apr 25: period if n ≤ Apr 25, luteal if n ≥ Apr 26.
    assert cb(d(4, 25)) == {"period", "luteal"}
    # Apr 11: in the window (n = Apr 23) or before it (n = May 1) — both follicular.
    assert cb(d(4, 11)) == {"follicular"}


def test_candidate_buckets_when_late_or_without_a_prediction():
    assert phases.candidate_buckets(d(5, 3), current(d(5, 2)), 5) == {"luteal", "period"}
    assert phases.candidate_buckets(d(4, 11), current(d(4, 10), lengths=[28, 30]), 5) is None
