"""Personal phase tracker (spec.md Feature 17; Appendix A is the reference).

Phases come from the user's own cycles, never a 28-day template, and are
always estimates:
- Completed cycles: ovulation is counted BACKWARDS from the next period
  start (N − L, L = the user's luteal_days), with a ±2-day window. The
  luteal half is the steadier one (Appendix A1–A2), so luteal days align
  to the next period and follicular days to this period's start.
- The current cycle has no next start yet, so its windows come from the
  Honest prediction's range E..T and are as wide as that uncertainty.

Four display phases (period, follicular, ovulation window, luteal); the
analysis groups them into three buckets — decision (b), DECISIONS.md.
Builds on predict.py (Honest prediction, LUTEAL_DAYS) rather than
re-deriving the fertile window.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

import db
import predict

PHASES = ("period", "follicular", "ovulation_window", "luteal")
PHASE_LABELS = {
    "period": "Period",
    "follicular": "Follicular",
    "ovulation_window": "Ovulation window",
    "luteal": "Luteal",
}
BUCKETS = ("period", "follicular", "luteal")
BUCKET_OF = {"period": "period", "follicular": "follicular",
             "ovulation_window": "follicular", "luteal": "luteal"}
BUCKET_LABELS = {
    "period": "period days",
    "follicular": "follicular phase (incl. the ovulation window)",
    "luteal": "luteal phase",
}
OVULATION_HALF_WINDOW = 2  # days either side of the estimate
DEFAULT_PERIOD_DAYS = 5  # only used before any period has been logged


def _days(n: int) -> timedelta:
    return timedelta(days=n)


def luteal(luteal_days: int | None) -> int:
    return predict.LUTEAL_DAYS if luteal_days is None else luteal_days


def period_end(start: date, bleeding_days: list[date]) -> date:
    """Last bleeding day of the period starting at `start`, using db.py's
    period rule (bleeds at most PERIOD_GAP_DAYS apart are one period)."""
    last = start
    for d in sorted(d for d in set(bleeding_days) if d >= start):
        if (d - last).days > db.PERIOD_GAP_DAYS:
            break
        last = d
    return last


def completed_cycle_phases(
    start: date, next_start: date, last_period_day: date, luteal_days: int | None = None
) -> dict[date, str]:
    """Phase of every day in a completed cycle [start, next_start).

    Ovulation estimate = next_start − L; window = that ± 2 days; luteal =
    the days after the window; follicular = between period and window.
    Where a short cycle makes them overlap, period wins, then luteal.
    """
    ovulation = next_start - _days(luteal(luteal_days))
    window_start = ovulation - _days(OVULATION_HALF_WINDOW)
    luteal_start = ovulation + _days(OVULATION_HALF_WINDOW + 1)
    phases = {}
    for k in range((next_start - start).days):
        d = start + _days(k)
        if d <= last_period_day:
            phases[d] = "period"
        elif d >= luteal_start:
            phases[d] = "luteal"
        elif d >= window_start:
            phases[d] = "ovulation_window"
        else:
            phases[d] = "follicular"
    return phases


def history_phases(
    starts: list[date], bleeding_days: list[date], luteal_days: int | None = None
) -> dict[date, str]:
    """Phase of every day in every completed cycle (the open cycle is left
    out: its phases are forward guesses, not used by the analysis)."""
    phases: dict[date, str] = {}
    for start, next_start in zip(starts, starts[1:]):
        phases.update(completed_cycle_phases(
            start, next_start, period_end(start, bleeding_days), luteal_days))
    return phases


def typical_period_days(starts: list[date], bleeding_days: list[date]) -> int:
    """Median period length (days, start to last bleed) of completed cycles."""
    lengths = [(period_end(s, bleeding_days) - s).days + 1 for s in starts[:-1]]
    return round(median(lengths)) if lengths else DEFAULT_PERIOD_DAYS


@dataclass(frozen=True)
class CurrentCycle:
    """Where today sits in the open cycle — estimates, shown as windows."""

    start: date
    day: int  # cycle day, 1-based
    period_end: date  # logged, or projected while the period is ongoing
    enough_data: bool  # False below predict.MIN_CYCLES: only the period is known
    late: bool = False  # past the predicted range, no new period logged
    next_earliest: date | None = None
    next_latest: date | None = None
    ovulation_from: date | None = None  # ovulation window, widened by the range
    ovulation_to: date | None = None
    luteal_from: date | None = None
    phase_today: str | None = None  # None = not sure (late, or not enough data)


def expected_period_end(start: date, last_bleed: date, today: date, period_days: int) -> date:
    """While a period looks ongoing (a bleed logged today or yesterday),
    assume it lasts the typical length; once it has stopped, it's what
    was logged."""
    if (today - last_bleed).days <= 1:
        return max(last_bleed, start + _days(period_days - 1))
    return last_bleed


def current_cycle(
    starts: list[date], bleeding_days: list[date], cycle_lengths: list[int],
    today: date, luteal_days: int | None = None, period_days: int | None = None,
) -> CurrentCycle | None:
    """The open cycle's phase windows, or None before any period is logged."""
    if not starts:
        return None
    start = starts[-1]
    if period_days is None:
        period_days = typical_period_days(starts, bleeding_days)
    last_bleed = period_end(start, [d for d in bleeding_days if d <= today])
    expected_end = expected_period_end(start, last_bleed, today, period_days)
    base = dict(start=start, day=(today - start).days + 1, period_end=expected_end)
    in_period = today <= expected_end
    prediction = predict.honest_prediction(cycle_lengths, start)
    if isinstance(prediction, predict.NotEnoughData):
        return CurrentCycle(**base, enough_data=False, phase_today="period" if in_period else None)
    L = luteal(luteal_days)
    e, t = prediction.earliest, prediction.latest
    window = dict(
        next_earliest=e, next_latest=t,
        ovulation_from=e - _days(L + OVULATION_HALF_WINDOW),
        ovulation_to=t - _days(L - OVULATION_HALF_WINDOW),
        luteal_from=t - _days(L - OVULATION_HALF_WINDOW - 1),
    )
    if in_period:
        phase = "period"
    elif today > t:
        return CurrentCycle(**base, enough_data=True, late=True, **window)
    elif today >= window["luteal_from"]:
        phase = "luteal"
    elif today >= window["ovulation_from"]:
        phase = "ovulation_window"
    else:
        phase = "follicular"
    return CurrentCycle(**base, enough_data=True, phase_today=phase, **window)


def candidate_buckets(
    day: date, current: CurrentCycle, period_days: int, luteal_days: int | None = None
) -> frozenset[str] | None:
    """Every analysis bucket `day` could fall in, given the uncertainty in
    the next period start (spec.md, LLM layer, Week Fit rule).

    Tries each possible next start n in the Honest range (never before
    `current`'s own last known day) and collects the bucket the day gets
    for each. None when there's no prediction.
    """
    if not current.enough_data:
        return None
    if current.late:
        return frozenset({"luteal", "period"})
    L = luteal(luteal_days)
    today = current.start + _days(current.day - 1)
    first = max(current.next_earliest, today)
    found = set()
    for k in range((current.next_latest - first).days + 1):
        n = first + _days(k)
        if day >= n:
            found.add("period" if (day - n).days < period_days else "follicular")
        elif day <= current.period_end:
            found.add("period")
        else:
            phase = completed_cycle_phases(current.start, n, current.period_end, L).get(day)
            found.add(BUCKET_OF[phase])
    return frozenset(found)
