"""Phase 3: Simple/Honest prediction and the fertile window.

The small examples are worked out by hand in the comments; the coverage
tests check the 90% interval against simulated people.
"""
from datetime import date, timedelta

import numpy as np
import pytest

import predict
import simulate

JAN1 = date(2026, 1, 1)


# --- minimum data -------------------------------------------------------------

@pytest.mark.parametrize("fn", [predict.simple_prediction, predict.honest_prediction])
def test_below_three_cycles_is_not_enough_data(fn):
    assert fn([28, 30], JAN1) == predict.NotEnoughData(have=2, need=3)
    assert fn([], JAN1) == predict.NotEnoughData(have=0, need=3)


# --- Simple -------------------------------------------------------------------

def test_simple_is_last_start_plus_mean():
    # mean(28, 30, 29) = 29 -> Jan 1 + 29 days = Jan 30
    p = predict.simple_prediction([28, 30, 29], JAN1)
    assert p.next_start == date(2026, 1, 30)
    assert p.mean_length == 29


def test_simple_rounds_half_up():
    # mean(28, 29, 28, 29) = 28.5 -> 29 days, not banker's-rounded 28
    assert predict.simple_prediction([28, 29, 28, 29], JAN1).next_start == date(2026, 1, 30)


def test_only_the_last_twelve_cycles_are_used():
    # A 60-day cycle long ago, then twelve 28s: only the 28s count.
    p = predict.simple_prediction([60] + [28] * 12, JAN1)
    assert p.next_start == date(2026, 1, 29)
    assert p.n_cycles == 12


# --- Honest -------------------------------------------------------------------

def test_honest_interval_by_hand():
    # lengths 28, 30, 29: mean 29, sd 1, n 3, t(0.95, df=2) = 2.91999
    # half-width = 2.91999 * 1 * sqrt(1 + 1/3) = 3.3717
    # interval 25.628 .. 32.372 days -> rounded outward to 25 .. 33 days
    # -> Jan 1 + 25 = Jan 26, Jan 1 + 33 = Feb 3
    lo, hi = predict.length_interval([28, 30, 29])
    assert lo == pytest.approx(25.628, abs=1e-3)
    assert hi == pytest.approx(32.372, abs=1e-3)
    p = predict.honest_prediction([28, 30, 29], JAN1)
    assert (p.earliest, p.latest) == (date(2026, 1, 26), date(2026, 2, 3))


def test_identical_cycles_still_get_a_range():
    # sd 0 would give a one-day "range"; it's widened to +/- 1 day:
    # 28 days -> 27 .. 29 -> Jan 28 .. Jan 30
    p = predict.honest_prediction([28, 28, 28], JAN1)
    assert (p.earliest, p.latest) == (date(2026, 1, 28), date(2026, 1, 30))


def test_late_only_after_the_whole_range():
    p = predict.honest_prediction([28, 30, 29], JAN1)  # Jan 26 .. Feb 3
    assert not predict.is_late(p, date(2026, 2, 3))
    assert predict.is_late(p, date(2026, 2, 4))


# --- fertile window -----------------------------------------------------------

def test_fertile_window_from_simple():
    # next start Jan 30 -> ovulation Jan 30 - 14 = Jan 16 -> window Jan 11 .. Jan 17
    w = predict.fertile_window(predict.simple_prediction([28, 30, 29], JAN1))
    assert (w.ovulation_earliest, w.ovulation_latest) == (date(2026, 1, 16), date(2026, 1, 16))
    assert (w.start, w.end) == (date(2026, 1, 11), date(2026, 1, 17))


def test_fertile_window_from_honest_spans_the_range():
    # range Jan 26 .. Feb 3 -> ovulation Jan 12 .. Jan 20 -> window Jan 7 .. Jan 21
    w = predict.fertile_window(predict.honest_prediction([28, 30, 29], JAN1))
    assert (w.ovulation_earliest, w.ovulation_latest) == (date(2026, 1, 12), date(2026, 1, 20))
    assert (w.start, w.end) == (date(2026, 1, 7), date(2026, 1, 21))


# --- coverage on simulated people ---------------------------------------------

def _coverage(irregular_rate: float, people: int = 2000) -> tuple[float, float]:
    """(continuous-interval coverage, shown-date-range coverage)."""
    continuous = shown = 0
    for seed in range(people):
        rng = np.random.default_rng(seed)
        n = int(rng.integers(3, 13))
        _, _, lengths, _ = simulate.simulate_lengths(rng, n + 1, irregular_rate)
        history, actual = lengths[:n], lengths[n]
        lo, hi = predict.length_interval(history)
        continuous += lo <= actual <= hi
        p = predict.honest_prediction(history, JAN1)
        shown += p.earliest <= JAN1 + timedelta(days=actual) <= p.latest
    return continuous / people, shown / people


def test_shown_range_covers_about_90_percent_with_irregular_cycles():
    # Plan acceptance, on the agreed simulation (15% irregular cycles).
    _, shown = _coverage(irregular_rate=0.15)
    assert 0.85 <= shown <= 0.95


def test_interval_method_is_calibrated_on_clean_data():
    # With no irregular cycles the t-interval's assumptions hold, so the
    # unrounded interval should cover close to its nominal 90%.
    continuous, _ = _coverage(irregular_rate=0.0)
    assert 0.88 <= continuous <= 0.93
