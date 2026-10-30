"""The 6-month gate (spec.md Feature 19).

The personalised features (by-phase findings, Phase Guide, Week Fit)
appear only after enough logging. All three must hold:
- the first logged day is at least GATE_DAYS (180) days before today;
- at least GATE_MIN_CYCLES (4) completed cycles — not 6, which would lock
  out long-but-normal cycles for 7–8 months (DECISIONS.md);
- at least GATE_MIN_LOGGED_DAYS (90, i.e. 50%) of the last 180 days have
  a log entry.
Before that the app shows progress, never a plan. Pure local logic.
"""
from dataclasses import dataclass
from datetime import date, timedelta

GATE_DAYS = 180
GATE_MIN_CYCLES = 4
GATE_MIN_LOGGED_SHARE = 0.5
GATE_MIN_LOGGED_DAYS = round(GATE_DAYS * GATE_MIN_LOGGED_SHARE)  # 90


@dataclass(frozen=True)
class Condition:
    label: str
    have: int
    need: int

    @property
    def met(self) -> bool:
        return self.have >= self.need


@dataclass(frozen=True)
class GateStatus:
    conditions: tuple[Condition, ...]

    @property
    def open(self) -> bool:
        return all(c.met for c in self.conditions)


def gate_status(logged_dates: list[date], completed_cycles: int, today: date) -> GateStatus:
    """Where the user stands on each condition (also drives the progress view)."""
    past = [d for d in logged_dates if d <= today]
    days_logging = (today - min(past)).days if past else 0
    window_start = today - timedelta(days=GATE_DAYS - 1)  # the last 180 days, today included
    recent = len({d for d in past if d >= window_start})
    return GateStatus((
        Condition("days since your first log", days_logging, GATE_DAYS),
        Condition("completed cycles", completed_cycles, GATE_MIN_CYCLES),
        Condition("days logged in the last 180", recent, GATE_MIN_LOGGED_DAYS),
    ))
