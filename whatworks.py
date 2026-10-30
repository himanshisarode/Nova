"""What works for me, by phase (spec.md Feature 20) — local statistics, no API.

For each (phase bucket, strategy): is the "how did today go" rating
different on days the strategy was used than on days it wasn't, inside
the same cycle and the same bucket (the user's own baseline)?

- Only rated days in completed cycles count (current-cycle phases are
  forward guesses).
- Minimum: MIN_USES use days, over MIN_CYCLES cycles that each also have
  a rated non-use day in that bucket. Below it: "not enough data yet".
- Test: stratified permutation test. Statistic = weighted mean over
  cycles of (mean use − mean non-use), weight n_use·n_non/(n_use+n_non).
  Null: shuffle use/non-use labels within each cycle only. Exact when
  there are ≤ EXACT_LIMIT arrangements, else N_PERMUTATIONS shuffles with
  a fixed seed. Two-sided.
- Benjamini–Hochberg across every tested pair, q < FDR_Q.

Associative only: a finding is a pattern in the user's logs, not a
cause (strategies are chosen by feel; nearby days affect each other;
phases are estimates). DECISIONS.md explains each choice.
"""
import itertools
import math
from dataclasses import dataclass
from datetime import date
from statistics import mean

import numpy as np

import db
import phases

MIN_USES = 8
MIN_CYCLES = 4
FDR_Q = 0.10
EXACT_LIMIT = 20_000
N_PERMUTATIONS = 5_000
SEED = 20261030  # fixed, so the same data always gives the same answer
TIERS = (  # (tier, q below, min cycles) — positives only, strongest first
    ("strong evidence", 0.01, 6),
    ("moderate evidence", 0.05, MIN_CYCLES),
    ("early sign", FDR_Q, MIN_CYCLES),
)
_TOL = 1e-9  # float tolerance when comparing shuffled statistics


@dataclass(frozen=True)
class RatedDay:
    day: date
    cycle: int  # index of the completed cycle it belongs to
    bucket: str  # one of phases.BUCKETS
    rating: int
    strategies: frozenset[str]


@dataclass(frozen=True)
class PairResult:
    bucket: str
    strategy: str
    uses: int  # use days in cycles that can be compared
    cycles: int  # cycles with both a use and a non-use rated day
    tested: bool
    statistic: float | None = None
    p_value: float | None = None
    q_value: float | None = None
    mean_with: float | None = None
    mean_without: float | None = None

    @property
    def verdict(self) -> str:
        if not self.tested:
            return "not_enough_data"
        if self.q_value < FDR_Q:
            return "tends_to_go_well" if self.statistic > 0 else "tended_lower"
        return "no_clear_difference"

    @property
    def tier(self) -> str | None:
        if self.verdict != "tends_to_go_well":
            return None
        for name, q_below, min_cycles in TIERS:
            if self.q_value < q_below and self.cycles >= min_cycles:
                return name
        return None


# --- data ---------------------------------------------------------------------

def rated_days(
    starts: list[date], logs: list[db.LogEntry], luteal_days: int | None = None
) -> list[RatedDay]:
    """Rated days in completed cycles, each with its analysis bucket."""
    bleeding = [e.date for e in logs if e.flow in db.BLEEDING_FLOWS]
    day_phase = phases.history_phases(starts, bleeding, luteal_days)
    cycle_of = {}
    for i, (a, b) in enumerate(zip(starts, starts[1:])):
        for k in range((b - a).days):
            cycle_of[date.fromordinal(a.toordinal() + k)] = i
    return [
        RatedDay(e.date, cycle_of[e.date], phases.BUCKET_OF[day_phase[e.date]], e.day_rating, e.strategies)
        for e in logs
        if e.day_rating is not None and e.date in day_phase
    ]


def _blocks(days: list[RatedDay], bucket: str, strategy: str) -> list[tuple[list[int], list[int]]]:
    """Per cycle: (ratings on use days, ratings on non-use days), only for
    cycles that have both."""
    by_cycle: dict[int, tuple[list[int], list[int]]] = {}
    for d in days:
        if d.bucket == bucket:
            use, non = by_cycle.setdefault(d.cycle, ([], []))
            (use if strategy in d.strategies else non).append(d.rating)
    return [by_cycle[c] for c in sorted(by_cycle) if all(by_cycle[c])]


# --- the test -------------------------------------------------------------------

def _weight(n_use: int, n_non: int) -> float:
    return n_use * n_non / (n_use + n_non)


def stratified_statistic(blocks: list[tuple[list[int], list[int]]]) -> float:
    """Weighted mean over cycles of (mean on use days − mean on non-use days)."""
    weights = [_weight(len(u), len(n)) for u, n in blocks]
    diffs = [mean(u) - mean(n) for u, n in blocks]
    return sum(w * x for w, x in zip(weights, diffs)) / sum(weights)


def _arrangements(blocks) -> int:
    return math.prod(math.comb(len(u) + len(n), len(u)) for u, n in blocks)


def stratified_p_value(blocks: list[tuple[list[int], list[int]]], seed: int = SEED) -> float:
    """Two-sided p-value: how often relabelling use/non-use days within each
    cycle gives a statistic at least as far from 0 as the real one."""
    observed = abs(stratified_statistic(blocks))
    weights = [_weight(len(u), len(n)) for u, n in blocks]
    total_weight = sum(weights)

    if _arrangements(blocks) <= EXACT_LIMIT:
        per_block = []  # every possible (mean use − mean non-use) for each cycle
        for u, n in blocks:
            values = u + n
            k, total = len(u), sum(u) + sum(n)
            per_block.append([
                sum(c) / k - (total - sum(c)) / (len(values) - k)
                for c in itertools.combinations(values, k)
            ])
        hits = count = 0
        for combo in itertools.product(*per_block):
            count += 1
            if abs(sum(w * x for w, x in zip(weights, combo)) / total_weight) >= observed - _TOL:
                hits += 1
        return hits / count

    rng = np.random.default_rng(seed)
    stats = np.zeros(N_PERMUTATIONS)
    for w, (u, n) in zip(weights, blocks):
        values = np.array(u + n, dtype=float)
        shuffled = rng.permuted(np.tile(values, (N_PERMUTATIONS, 1)), axis=1)
        k = len(u)
        stats += w * (shuffled[:, :k].mean(axis=1) - shuffled[:, k:].mean(axis=1))
    stats /= total_weight
    hits = int(np.sum(np.abs(stats) >= observed - _TOL))
    return (1 + hits) / (1 + N_PERMUTATIONS)


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """BH-adjusted q-values, in the input order."""
    m = len(p_values)
    order = sorted(range(m), key=lambda i: p_values[i])
    q = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        running = min(running, p_values[i] * m / rank)
        q[i] = running
    return q


def analyse(days: list[RatedDay]) -> list[PairResult]:
    """Every (bucket, strategy) pair: tested ones carry p, q and a verdict."""
    pending = []
    results: dict[tuple[str, str], PairResult] = {}
    for bucket in phases.BUCKETS:
        for strategy in db.STRATEGIES:
            blocks = _blocks(days, bucket, strategy)
            uses = sum(len(u) for u, _ in blocks)
            base = dict(bucket=bucket, strategy=strategy, uses=uses, cycles=len(blocks))
            if uses < MIN_USES or len(blocks) < MIN_CYCLES:
                results[(bucket, strategy)] = PairResult(**base, tested=False)
                continue
            pending.append((base, blocks))
    p_values = [stratified_p_value(b) for _, b in pending]
    q_values = benjamini_hochberg(p_values)
    for (base, blocks), p, q in zip(pending, p_values, q_values):
        results[(base["bucket"], base["strategy"])] = PairResult(
            **base, tested=True,
            statistic=stratified_statistic(blocks),
            p_value=p,
            q_value=q,
            mean_with=mean(r for u, _ in blocks for r in u),
            mean_without=mean(r for _, n in blocks for r in n),
        )
    return [results[(b, s)] for b in phases.BUCKETS for s in db.STRATEGIES]


def goes_well(results: list[PairResult]) -> dict[str, list[tuple[str, str]]]:
    """{bucket: [(strategy, tier), ...]} for findings that tend to go well,
    strongest first — the only thing the LLM layer is ever given."""
    out: dict[str, list[tuple[str, str]]] = {b: [] for b in phases.BUCKETS}
    for r in sorted(results, key=lambda r: (r.q_value if r.tested else 2, r.strategy)):
        if r.verdict == "tends_to_go_well":
            out[r.bucket].append((r.strategy, r.tier))
    return out


# --- wording ----------------------------------------------------------------------

def strategy_label(strategy: str) -> str:
    return {"rest_day": "a rest day", "deep_focus_work": "deep-focus work",
            "light_admin": "light admin tasks", "social_plans": "social plans",
            "early_night": "an early night", "strength": "strength training",
            "walk": "a walk", "cardio": "cardio"}.get(strategy, strategy.replace("_", " "))


def describe(r: PairResult) -> str:
    """The plain, associative sentence the app shows for one pair."""
    what, when = strategy_label(r.strategy), phases.BUCKET_LABELS[r.bucket]
    if r.verdict == "not_enough_data":
        return (f"{what.capitalize()} in your {when}: not enough data yet — {r.uses} of "
                f"{MIN_USES} days over {r.cycles} of {MIN_CYCLES} cycles.")
    if r.verdict == "no_clear_difference":
        return f"{what.capitalize()} in your {when}: no clear difference in how your days went."
    direction = "higher" if r.verdict == "tends_to_go_well" else "lower"
    tier = f" ({r.tier})" if r.tier else ""
    return (f"In your data, days with {what} during your {when} tended to be rated "
            f"{direction} ({r.mean_with:.1f} vs {r.mean_without:.1f} out of 5){tier}.")
