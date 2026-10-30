"""Synthetic cycle histories with known ground truth, for testing.

Each simulated person gets a typical cycle length ~ N(29, 2) days and a
cycle-to-cycle spread of 1–3 days. A share of cycles (default 15%) are
deliberately made irregular by shifting them 10–20 days longer or
shorter; which ones is recorded, so detection can be scored against the
truth. Optionally, irregular cycles get far more high-stress days logged
— a planted association for the SHAP explanation to find.

Daily logs are generated so that db.period_starts() recovers exactly the
simulated cycles (tests/test_simulate.py checks this).
"""
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np

from db import LogEntry

TYPICAL_LENGTH_MEAN = 29.0
TYPICAL_LENGTH_SD = 2.0
SPREAD_RANGE = (1.0, 3.0)
IRREGULAR_SHIFT_RANGE = (10, 20)  # days, inclusive
MIN_LENGTH = 14  # keeps every period separated by well over the 7-day gap
PERIOD_DAYS_RANGE = (4, 6)  # bleeding days, inclusive

# Per-day probability of each lifestyle tag.
TAG_RATES = {"poor_sleep": 0.10, "high_stress": 0.08, "travel": 0.05}
LINKED_STRESS_RATE = 0.50  # high_stress rate inside irregular cycles when stress_link=True


@dataclass(frozen=True)
class SimulatedHistory:
    typical_length: float
    spread: float
    lengths: list[int]
    irregular: list[bool]  # ground truth, one per cycle
    starts: list[date]  # period starts: one per cycle plus the open cycle's
    logs: list[LogEntry]


def simulate_lengths(
    rng: np.random.Generator, n_cycles: int, irregular_rate: float = 0.15
) -> tuple[float, float, list[int], list[bool]]:
    """(typical length, spread, cycle lengths, which cycles are irregular)."""
    typical = rng.normal(TYPICAL_LENGTH_MEAN, TYPICAL_LENGTH_SD)
    spread = rng.uniform(*SPREAD_RANGE)
    lengths, irregular = [], []
    for _ in range(n_cycles):
        length = round(rng.normal(typical, spread))
        is_irregular = bool(rng.random() < irregular_rate)
        if is_irregular:
            shift = int(rng.integers(IRREGULAR_SHIFT_RANGE[0], IRREGULAR_SHIFT_RANGE[1] + 1))
            length += shift if rng.random() < 0.5 else -shift
        lengths.append(max(MIN_LENGTH, length))
        irregular.append(is_irregular)
    return typical, spread, lengths, irregular


def simulate_logs(
    rng: np.random.Generator,
    starts: list[date],
    irregular: list[bool],
    stress_link: bool = False,
) -> list[LogEntry]:
    """One log per day from the first start through the last period.

    `starts` has one more entry than `irregular`: the last is the open
    cycle's start, logged with a period so every earlier cycle completes.
    """
    logs = []
    for i, start in enumerate(starts):
        is_last = i == len(starts) - 1
        cycle_days = PERIOD_DAYS_RANGE[1] if is_last else (starts[i + 1] - start).days
        period_days = int(rng.integers(PERIOD_DAYS_RANGE[0], PERIOD_DAYS_RANGE[1] + 1))
        stress_rate = (
            LINKED_STRESS_RATE if stress_link and not is_last and irregular[i]
            else TAG_RATES["high_stress"]
        )
        for offset in range(cycle_days):
            day = start + timedelta(days=offset)
            in_period = offset < period_days
            if in_period:
                flow = "heavy" if offset < 2 else "medium" if offset < 4 else "light"
            elif offset == cycle_days - 1 and not is_last and rng.random() < 0.2:
                flow = "spotting"  # the day before a period; must not start one
            else:
                flow = "none"
            symptoms = set()
            if in_period and rng.random() < 0.6:
                symptoms.add("cramps")
            if rng.random() < (0.3 if in_period else 0.08):
                symptoms.add("fatigue")
            logs.append(LogEntry(
                date=day,
                flow=flow,
                mood=int(rng.integers(1, 4) if in_period else rng.integers(2, 6)),
                symptoms=frozenset(symptoms),
                poor_sleep=bool(rng.random() < TAG_RATES["poor_sleep"]),
                high_stress=bool(rng.random() < stress_rate),
                travel=bool(rng.random() < TAG_RATES["travel"]),
            ))
    return logs


def simulate_history(
    seed: int,
    n_cycles: int = 12,
    irregular_rate: float = 0.15,
    stress_link: bool = False,
    first_start: date = date(2025, 1, 1),
) -> SimulatedHistory:
    """A complete simulated person: cycle lengths, ground truth, and daily logs."""
    rng = np.random.default_rng(seed)
    typical, spread, lengths, irregular = simulate_lengths(rng, n_cycles, irregular_rate)
    starts = [first_start]
    for length in lengths:
        starts.append(starts[-1] + timedelta(days=length))
    logs = simulate_logs(rng, starts, irregular, stress_link)
    return SimulatedHistory(typical, spread, lengths, irregular, starts, logs)


# --- Level 2: "what works for me" days (spec.md Features 18, 20) ---------------
# Kept on its own random stream (seeded from [seed, LEVEL2_STREAM]) so every
# number the functions above produce is unchanged.
LEVEL2_STREAM = 2
STRATEGY_USE_RATE = 0.25  # chance of ticking each strategy on a given day
RATING_LOG_RATE = 0.85  # share of days with a "how did today go" rating
RATING_BASE = 3.0
CYCLE_LEVEL_SD = 0.4  # some months just go better than others
DAY_NOISE_SD = 0.8


def with_strategies(
    history: SimulatedHistory,
    seed: int,
    effects: dict[tuple[str, str], float] | None = None,
    luteal_days: int | None = None,
) -> list[LogEntry]:
    """The history's logs plus day ratings, energy and strategies.

    `effects` plants an association: {(bucket, strategy): rating points
    added on days that strategy is used in that phase bucket}. Phases are
    the tracker's own estimates (phases.history_phases), so a planted
    effect is exactly what the analysis can, at best, recover.
    """
    import phases  # local: simulate.py stays importable without the tracker

    effects = effects or {}
    rng = np.random.default_rng([seed, LEVEL2_STREAM])
    from db import BLEEDING_FLOWS, STRATEGIES

    bleeding = [e.date for e in history.logs if e.flow in BLEEDING_FLOWS]
    day_phase = phases.history_phases(history.starts, bleeding, luteal_days)
    cycle_level = [rng.normal(0, CYCLE_LEVEL_SD) for _ in history.starts]
    cycle_index = 0
    out = []
    for entry in history.logs:
        while cycle_index + 1 < len(history.starts) and entry.date >= history.starts[cycle_index + 1]:
            cycle_index += 1
        used = frozenset(s for s in STRATEGIES if rng.random() < STRATEGY_USE_RATE)
        bucket = phases.BUCKET_OF.get(day_phase.get(entry.date))
        score = RATING_BASE + cycle_level[cycle_index] + rng.normal(0, DAY_NOISE_SD)
        score += sum(effects.get((bucket, s), 0.0) for s in used)
        rated = rng.random() < RATING_LOG_RATE
        out.append(LogEntry(
            entry.date, entry.flow, entry.mood, entry.symptoms,
            entry.poor_sleep, entry.high_stress, entry.travel,
            day_rating=int(min(5, max(1, round(score)))) if rated else None,
            energy=int(min(5, max(1, round(score + rng.normal(0, 0.7))))) if rated else None,
            strategies=used,
        ))
    return out
