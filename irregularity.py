"""Irregular-cycle flags and SHAP explanations (spec.md Feature 5).

Flagging is a transparent rule, not a model. A completed cycle is
irregular if:
  (a) its length is outside 24–38 days (FIGO 2018 normal frequency), or
  (b) it's more than 7 days from the median of your previous cycles
      (needs at least 3 earlier cycles; uses up to the last 12).

The explanation is separate and per-user: a small random forest learns
which logged factors (share of days with each lifestyle tag, average
mood, share of days with symptoms) go with your flagged cycles, and SHAP
says which factors pushed each flagged cycle toward "irregular". It only
runs with at least 3 flagged and 3 unflagged cycles — below that, any
"pattern" would be noise. Results are associations, never causes.

SHAP alone always names *some* factor, even when nothing real is going
on, so a factor is only shown if flagged and unflagged cycles also
differ on it significantly: a permutation test on the difference in
means, at 0.05 split across the factors tested (Bonferroni). Without
that gate, simulated users with no real pattern got an explanation for
every flagged cycle; with it, about 7% of such users get one.
"""
import math
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import median

from db import BLEEDING_FLOWS, LIFESTYLE_TAGS, Cycle, LogEntry

NORMAL_RANGE = (24, 38)
MAX_DEVIATION_DAYS = 7
MIN_PRIOR_CYCLES = 3
PRIOR_WINDOW = 12
MIN_PER_GROUP = 3  # flagged and unflagged cycles needed before explaining
FAMILY_ALPHA = 0.05  # shared across all factors tested
PERMUTATIONS = 2000

FEATURES: tuple[str, ...] = (*LIFESTYLE_TAGS, "mean_mood", "symptom_days")
FEATURE_LABELS = {
    "poor_sleep": "poor-sleep days",
    "high_stress": "high-stress days",
    "travel": "travel days",
    "mean_mood": "average mood",
    "symptom_days": "days with symptoms",
}
NEUTRAL_MOOD = 3.0


@dataclass(frozen=True)
class CycleAssessment:
    start: date
    length: int
    outside_range: bool
    usual: float | None  # median of previous cycles, if there were enough
    deviation: float | None  # length - usual

    @property
    def irregular(self) -> bool:
        return self.outside_range or (
            self.deviation is not None and abs(self.deviation) > MAX_DEVIATION_DAYS
        )

    @property
    def message(self) -> str:
        """Plain-language reason, e.g. "41 days — 12 days longer than your usual 29"."""
        reasons = []
        if self.deviation is not None and abs(self.deviation) > MAX_DEVIATION_DAYS:
            direction = "longer" if self.deviation > 0 else "shorter"
            reasons.append(
                f"{abs(self.deviation):.0f} days {direction} than your usual {self.usual:.0f}"
            )
        if self.outside_range:
            direction = "longer" if self.length > NORMAL_RANGE[1] else "shorter"
            reasons.append(
                f"{direction} than the {NORMAL_RANGE[0]}–{NORMAL_RANGE[1]} day range "
                "that's typical for adults"
            )
        return f"{self.length} days — " + "; ".join(reasons) if reasons else f"{self.length} days"


@dataclass(frozen=True)
class NotEnoughFlags:
    flagged: int
    unflagged: int
    need: int = MIN_PER_GROUP


@dataclass(frozen=True)
class FlagExplanation:
    start: date
    # (feature, SHAP contribution toward "irregular"), largest first; only
    # factors that pushed toward the flag are kept.
    factors: list[tuple[str, float]]

    @property
    def message(self) -> str:
        if not self.factors:
            return "No logged factor stood out for this cycle."
        names = [FEATURE_LABELS[f] for f, _ in self.factors[:2]]
        return (
            "Across your cycles, irregular ones tended to differ in "
            + " and ".join(names)
            + " — an association in your logs, not proof of a cause."
        )


def assess_cycles(cycles: list[Cycle]) -> list[CycleAssessment]:
    """One assessment per completed cycle, oldest first."""
    out = []
    for i, cycle in enumerate(cycles):
        prior = [c.length for c in cycles[max(0, i - PRIOR_WINDOW):i]]
        usual = median(prior) if len(prior) >= MIN_PRIOR_CYCLES else None
        out.append(CycleAssessment(
            start=cycle.start,
            length=cycle.length,
            outside_range=not NORMAL_RANGE[0] <= cycle.length <= NORMAL_RANGE[1],
            usual=usual,
            deviation=None if usual is None else cycle.length - usual,
        ))
    return out


def cycle_features(cycles: list[Cycle], logs: list[LogEntry]) -> list[dict[str, float]]:
    """Per-cycle features for the explainer, over each cycle's non-bleeding days.

    Bleeding days are left out because mood and symptoms shift during a
    period: otherwise a long cycle would look calmer simply because its
    period is a smaller share of it — a fake "factor" that's really just
    cycle length. Unlogged days count as tag-free.
    """
    by_day = {entry.date: entry for entry in logs}
    rows, moods = [], []
    for cycle in cycles:
        days = [by_day.get(cycle.start + timedelta(days=k)) for k in range(cycle.length)]
        days = [d for d in days if d is None or d.flow not in BLEEDING_FLOWS]
        logged = [d for d in days if d is not None]
        n = max(1, len(days))
        row = {tag: sum(getattr(d, tag) for d in logged) / n for tag in LIFESTYLE_TAGS}
        row["symptom_days"] = sum(bool(d.symptoms) for d in logged) / n
        cycle_moods = [d.mood for d in logged if d.mood is not None]
        row["mean_mood"] = sum(cycle_moods) / len(cycle_moods) if cycle_moods else math.nan
        moods += cycle_moods
        rows.append(row)
    fill = sum(moods) / len(moods) if moods else NEUTRAL_MOOD
    for row in rows:
        if math.isnan(row["mean_mood"]):
            row["mean_mood"] = fill
    return rows


def explain_flags(
    assessments: list[CycleAssessment], features: list[dict[str, float]]
) -> list[FlagExplanation] | NotEnoughFlags:
    """SHAP explanation for each flagged cycle, or NotEnoughFlags."""
    labels = [a.irregular for a in assessments]
    flagged = sum(labels)
    if flagged < MIN_PER_GROUP or len(labels) - flagged < MIN_PER_GROUP:
        return NotEnoughFlags(flagged=flagged, unflagged=len(labels) - flagged)

    # Imported here: shap takes several seconds to import and most pages
    # never need it.
    import numpy as np
    import shap
    from sklearn.ensemble import RandomForestClassifier

    x = np.array([[row[f] for f in FEATURES] for row in features])
    y = np.array(labels, dtype=bool)
    significant = {f for j, f in enumerate(FEATURES) if _differs(x[y, j], x[~y, j])}

    model = RandomForestClassifier(n_estimators=200, max_depth=3, random_state=0).fit(x, y)
    values = np.asarray(shap.TreeExplainer(model).shap_values(x))
    if values.ndim == 3:  # (cycles, features, classes) -> contributions to class 1
        values = values[..., 1]

    out = []
    for i, assessment in enumerate(assessments):
        if not assessment.irregular:
            continue
        pushes = [
            (f, float(v)) for f, v in zip(FEATURES, values[i]) if v > 0 and f in significant
        ]
        out.append(FlagExplanation(assessment.start, sorted(pushes, key=lambda p: -p[1])))
    return out


def _differs(flagged, unflagged) -> bool:
    """Permutation test on the difference in means, Bonferroni-corrected."""
    import numpy as np
    from scipy import stats

    result = stats.permutation_test(
        (flagged, unflagged),
        lambda a, b, axis: np.mean(a, axis=axis) - np.mean(b, axis=axis),
        n_resamples=PERMUTATIONS,
        vectorized=True,
        rng=np.random.default_rng(0),
    )
    return result.pvalue < FAMILY_ALPHA / len(FEATURES)
