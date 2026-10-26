"""Phase 3: irregularity flags (hand-checked rule) and SHAP explanations."""
from datetime import date, timedelta

import pytest

import db
import irregularity
import simulate


def cycles_of(lengths, first=date(2026, 1, 1)):
    starts = [first]
    for length in lengths:
        starts.append(starts[-1] + timedelta(days=length))
    return db.cycles_from_starts(starts)


def assess(lengths):
    return irregularity.assess_cycles(cycles_of(lengths))


# --- the rule, by hand --------------------------------------------------------

def test_long_cycle_flagged_on_both_counts():
    # usual = median(29, 28, 30) = 29; 41 is 12 over (> 7) and above 38.
    last = assess([29, 28, 30, 41])[-1]
    assert last.irregular and last.outside_range
    assert last.usual == 29 and last.deviation == 12
    assert last.message == (
        "41 days — 12 days longer than your usual 29; "
        "longer than the 24–38 day range that's typical for adults"
    )


def test_seven_days_from_usual_is_not_flagged_eight_is():
    assert not assess([29, 28, 30, 36])[-1].irregular  # 7 over, inside 24–38
    flagged = assess([29, 28, 30, 37])[-1]  # 8 over, still inside 24–38
    assert flagged.irregular and not flagged.outside_range
    assert flagged.message == "37 days — 8 days longer than your usual 29"


def test_shorter_than_usual():
    last = assess([33, 34, 33, 25])[-1]  # usual 33, 8 under, inside range
    assert last.irregular
    assert last.message == "25 days — 8 days shorter than your usual 33"


@pytest.mark.parametrize("length, flagged", [(23, True), (24, False), (38, False), (39, True)])
def test_range_boundaries(length, flagged):
    # A first cycle has no history, so only the 24–38 range applies.
    first = assess([length])[0]
    assert first.usual is None
    assert first.irregular is flagged


def test_usual_needs_three_earlier_cycles():
    # Third cycle has only 2 before it: 20 days later than usual isn't
    # judged against a "usual" yet, only against the range (37 is inside).
    a = assess([28, 29, 37])
    assert a[2].usual is None and not a[2].irregular


def test_usual_uses_only_the_last_twelve():
    # Twelve old 40s, then twelve 28s: the 25th cycle's usual is 28.
    a = assess([40] * 12 + [28] * 12 + [28])
    assert a[-1].usual == 28


# --- detection on simulated people -------------------------------------------

def test_recall_and_false_flag_rate_on_simulated_people():
    tp = fn = fp = tn = 0
    for seed in range(500):
        h = simulate.simulate_history(seed, n_cycles=12)
        for a, truth in zip(irregularity.assess_cycles(cycles_of(h.lengths)), h.irregular):
            if truth:
                tp += a.irregular
                fn += not a.irregular
            else:
                fp += a.irregular
                tn += not a.irregular
    assert tp / (tp + fn) >= 0.80  # plan acceptance
    assert fp / (fp + tn) <= 0.10  # guard: flagging everything can't pass


# --- features -----------------------------------------------------------------

def test_features_skip_bleeding_days():
    # 10-day cycle (feature calc only; real cycles can't be this short):
    # 3 bleeding days, 7 non-bleeding. Stress on 1 bleeding day and 2
    # non-bleeding days -> 2/7. Mood only counts non-bleeding days.
    start = date(2026, 1, 1)
    logs = [
        db.LogEntry(start + timedelta(days=k),
                    flow="heavy" if k < 3 else "none",
                    mood=1 if k < 3 else 4,
                    high_stress=k in (0, 5, 6))
        for k in range(10)
    ]
    row = irregularity.cycle_features([db.Cycle(start, start + timedelta(days=9), 10)], logs)[0]
    assert row["high_stress"] == pytest.approx(2 / 7)
    assert row["mean_mood"] == 4


# --- explanations -------------------------------------------------------------

def test_no_explanation_below_three_flagged():
    a = assess([29, 28, 30, 41, 29, 28, 45])  # 2 flagged
    features = [dict.fromkeys(irregularity.FEATURES, 0.0) for _ in a]
    assert irregularity.explain_flags(a, features) == irregularity.NotEnoughFlags(
        flagged=2, unflagged=5
    )


def _explanations(stress_link, seeds):
    for seed in seeds:
        h = simulate.simulate_history(seed, n_cycles=24, irregular_rate=0.3, stress_link=stress_link)
        cycles = db.cycles_from_starts(h.starts)  # real dates, so logs line up
        result = irregularity.explain_flags(
            irregularity.assess_cycles(cycles), irregularity.cycle_features(cycles, h.logs)
        )
        if isinstance(result, list):
            yield result


def test_planted_stress_link_is_found():
    found = [
        sum(bool(e.factors) and e.factors[0][0] == "high_stress" for e in result) > len(result) / 2
        for result in _explanations(stress_link=True, seeds=range(30))
    ]
    assert sum(found) / len(found) >= 0.80


def test_no_pattern_rarely_gets_an_explanation():
    # Negative control: nothing planted. SHAP alone would name a factor
    # for every flagged cycle; the significance gate must keep that rare.
    explained = [
        any(e.factors for e in result)
        for result in _explanations(stress_link=False, seeds=range(30))
    ]
    assert sum(explained) / len(explained) <= 0.15
