"""Period prediction and fertile-window estimate (spec.md Features 2–3).

Two modes over the same data:
- Simple: one date, last start + the average cycle length.
- Honest: a 90% prediction interval for the next cycle's length, from the
  t-distribution — mean ± t * sd * sqrt(1 + 1/n) — turned into a date
  range by rounding outward to whole days.

Both need MIN_CYCLES completed cycles; below that the answer is "not
enough data yet", never a guessed default like 28 days. Every completed
cycle counts, irregular ones included: if your cycles vary a lot, the
range should honestly be wide.
"""
import math
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean, stdev

from scipy import stats

MIN_CYCLES = 3
MAX_CYCLES_USED = 12  # the most recent ones; older history matters less
INTERVAL_LEVEL = 0.90
MIN_HALF_WIDTH_DAYS = 1  # never claim single-day certainty
# Fertile window: ovulation ~14 days before the next period (the luteal
# phase is the more stable half of the cycle), window 5 days before to
# 1 day after ovulation.
LUTEAL_DAYS = 14
FERTILE_DAYS_BEFORE = 5
FERTILE_DAYS_AFTER = 1


@dataclass(frozen=True)
class NotEnoughData:
    have: int
    need: int = MIN_CYCLES


@dataclass(frozen=True)
class SimplePrediction:
    next_start: date
    mean_length: float
    n_cycles: int


@dataclass(frozen=True)
class HonestPrediction:
    earliest: date
    latest: date
    mean_length: float
    n_cycles: int


@dataclass(frozen=True)
class FertileWindow:
    """An estimate, not contraception — spec.md Feature 3."""

    start: date
    end: date
    ovulation_earliest: date
    ovulation_latest: date


def _recent(lengths: list[int]) -> list[int]:
    return list(lengths)[-MAX_CYCLES_USED:]


# FIGO 2018 counts a shortest-to-longest spread of up to 7–9 days as
# regular; using the lenient end, only clearly-varying cycles trigger this.
MAX_NORMAL_VARIATION_DAYS = 9


def cycle_variation(lengths: list[int]) -> int:
    """Longest minus shortest of the cycles predictions use (last 12)."""
    used = _recent(lengths)
    return max(used) - min(used) if used else 0


def varies_a_lot(lengths: list[int]) -> bool:
    """True when recent cycles vary by more than MAX_NORMAL_VARIATION_DAYS.

    The fertile window then spans most of the cycle and stops being useful,
    so the app suggests talking to a doctor instead of showing dates.
    """
    return len(lengths) >= MIN_CYCLES and cycle_variation(lengths) > MAX_NORMAL_VARIATION_DAYS


def length_interval(lengths: list[int], level: float = INTERVAL_LEVEL) -> tuple[float, float]:
    """Prediction interval for the next cycle length (continuous, unrounded)."""
    n = len(lengths)
    if n < 2:
        raise ValueError("need at least 2 cycle lengths for an interval")
    m, s = mean(lengths), stdev(lengths)
    t = stats.t.ppf((1 + level) / 2, df=n - 1)
    half = t * s * math.sqrt(1 + 1 / n)
    return m - half, m + half


def simple_prediction(lengths: list[int], last_start: date) -> SimplePrediction | NotEnoughData:
    """One estimated date for the next period start."""
    if len(lengths) < MIN_CYCLES:
        return NotEnoughData(have=len(lengths))
    used = _recent(lengths)
    m = mean(used)
    # Round half up (Python's round() would send 28.5 to 28).
    return SimplePrediction(last_start + timedelta(days=math.floor(m + 0.5)), m, len(used))


def honest_prediction(lengths: list[int], last_start: date) -> HonestPrediction | NotEnoughData:
    """A date range the next period start should fall in, about 90% of the time."""
    if len(lengths) < MIN_CYCLES:
        return NotEnoughData(have=len(lengths))
    used = _recent(lengths)
    m = mean(used)
    lo, hi = length_interval(used)
    lo_days, hi_days = math.floor(lo), math.ceil(hi)
    center = math.floor(m + 0.5)
    lo_days = min(lo_days, center - MIN_HALF_WIDTH_DAYS)
    hi_days = max(hi_days, center + MIN_HALF_WIDTH_DAYS)
    return HonestPrediction(
        last_start + timedelta(days=lo_days),
        last_start + timedelta(days=hi_days),
        m,
        len(used),
    )


def is_late(prediction: SimplePrediction | HonestPrediction, today: date) -> bool:
    """True once today is past the predicted date/range — show "later than
    your usual range" instead of a stale prediction."""
    latest = prediction.latest if isinstance(prediction, HonestPrediction) else prediction.next_start
    return today > latest


def fertile_window(
    prediction: SimplePrediction | HonestPrediction, luteal_days: int | None = None
) -> FertileWindow:
    """Estimated fertile window for the current cycle.

    `luteal_days` is the user's setting (spec.md Feature 3); None means
    the default LUTEAL_DAYS, exactly as before the setting existed.
    """
    luteal = LUTEAL_DAYS if luteal_days is None else luteal_days
    if isinstance(prediction, HonestPrediction):
        earliest, latest = prediction.earliest, prediction.latest
    else:
        earliest = latest = prediction.next_start
    ov_earliest = earliest - timedelta(days=luteal)
    ov_latest = latest - timedelta(days=luteal)
    return FertileWindow(
        start=ov_earliest - timedelta(days=FERTILE_DAYS_BEFORE),
        end=ov_latest + timedelta(days=FERTILE_DAYS_AFTER),
        ovulation_earliest=ov_earliest,
        ovulation_latest=ov_latest,
    )
