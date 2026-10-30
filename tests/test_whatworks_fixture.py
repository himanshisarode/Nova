"""Phase 11: hand-built fixture for the by-phase analysis (spec.md Feature 20).

FIXED once written — like test_lifestyle_link.py, don't regenerate or
rewrite it. Every expected number is worked out by hand in the comments
below, independently of whatworks.py; the code has to match the hand
arithmetic, not the other way round.

The fixture (4 completed cycles, built directly as RatedDay rows):

  follicular, each cycle: 4 rated days, ratings 5, 5, 3, 3
    - yoga on the two 5s          → PLANTED effect
    - walk on one 5 and one 3     → NEGATIVE CONTROL (no effect)
  luteal, each cycle: 4 rated days, all rated 4
    - strength: 2, 2, 2, 1 days   → 7 uses: below the 8-use minimum
    - cardio:   3, 3, 2, 0 days   → 8 uses but only 3 cycles: below minimum
"""
from datetime import date, timedelta
from fractions import Fraction

import pytest

import whatworks
from whatworks import RatedDay

BASE = date(2026, 1, 1)


def fixture_days() -> list[RatedDay]:
    days, n = [], 0

    def add(cycle, bucket, rating, *strategies):
        nonlocal n
        days.append(RatedDay(BASE + timedelta(days=n), cycle, bucket, rating, frozenset(strategies)))
        n += 1

    strength = [2, 2, 2, 1]
    cardio = [3, 3, 2, 0]
    for c in range(4):
        add(c, "follicular", 5, "yoga", "walk")
        add(c, "follicular", 5, "yoga")
        add(c, "follicular", 3, "walk")
        add(c, "follicular", 3)
        for k in range(4):
            tags = []
            if k < strength[c]:
                tags.append("strength")
            if k < cardio[c]:
                tags.append("cardio")
            add(c, "luteal", 4, *tags)
    return days


def result(results, bucket, strategy):
    return next(r for r in results if r.bucket == bucket and r.strategy == strategy)


@pytest.fixture(scope="module")
def results():
    return whatworks.analyse(fixture_days())


# --- planted effect: yoga in the follicular phase ---------------------------------
# Each cycle: use {5, 5} mean 5, non-use {3, 3} mean 3 → difference 2.
# Weights all 2·2/4 = 1 → statistic = 2.
# Exact null: per cycle, C(4, 2) = 6 ways to pick the 2 "use" days:
#   {5,5} → +2 (1 way), {3,3} → −2 (1 way), one of each → 0 (4 ways).
# Total 6^4 = 1296 arrangements (≤ 20,000, so enumerated exactly).
# |T| ≥ 2 only if every cycle is +2 or every cycle is −2: 2 arrangements.
# p = 2 / 1296 = 1/648.

def test_planted_effect_statistic_and_exact_p(results):
    r = result(results, "follicular", "yoga")
    assert r.tested and r.uses == 8 and r.cycles == 4
    assert r.statistic == pytest.approx(2.0)
    assert r.p_value == pytest.approx(float(Fraction(2, 1296)))
    assert (r.mean_with, r.mean_without) == (5, 3)


# --- negative control: walk in the follicular phase ------------------------------
# Each cycle: use {5, 3} mean 4, non-use {5, 3} mean 4 → difference 0.
# Statistic 0; every arrangement has |T| ≥ 0, so p = 1.

def test_negative_control_finds_nothing(results):
    r = result(results, "follicular", "walk")
    assert r.tested and r.uses == 8 and r.cycles == 4
    assert r.statistic == pytest.approx(0.0)
    assert r.p_value == pytest.approx(1.0)
    assert r.verdict == "no_clear_difference" and r.tier is None


# --- multiple comparisons ----------------------------------------------------------
# Only yoga and walk (follicular) meet the minimum, so m = 2.
# BH: sorted p = [1/648 (yoga), 1 (walk)].
#   walk (rank 2): q = 1 · 2/2 = 1
#   yoga (rank 1): q = min(1/648 · 2/1, 1) = 1/324 ≈ 0.00309
# yoga: q < 0.10 and positive → "tends to go well";
#   q < 0.01 but only 4 cycles (< 6) → not "strong"; q < 0.05 → "moderate evidence".

def test_benjamini_hochberg_and_tier(results):
    yoga = result(results, "follicular", "yoga")
    walk = result(results, "follicular", "walk")
    assert yoga.q_value == pytest.approx(float(Fraction(1, 324)))
    assert walk.q_value == pytest.approx(1.0)
    assert yoga.verdict == "tends_to_go_well"
    assert yoga.tier == "moderate evidence"
    assert sum(r.tested for r in results) == 2


def test_only_the_planted_effect_reaches_the_llm_layer(results):
    assert whatworks.goes_well(results) == {
        "period": [], "follicular": [("yoga", "moderate evidence")], "luteal": [],
    }


# --- below the minimum: no number at all ------------------------------------------
# strength (luteal): 2 + 2 + 2 + 1 = 7 uses < 8.
# cardio (luteal): 3 + 3 + 2 = 8 uses, but cycle 4 has none → 3 cycles < 4.

def test_below_minimum_pairs_are_not_tested(results):
    strength = result(results, "luteal", "strength")
    cardio = result(results, "luteal", "cardio")
    assert (strength.uses, strength.cycles, strength.tested) == (7, 4, False)
    assert (cardio.uses, cardio.cycles, cardio.tested) == (8, 3, False)
    for r in (strength, cardio):
        assert r.verdict == "not_enough_data"
        assert r.p_value is None and r.statistic is None and r.mean_with is None
    assert "not enough data yet" in whatworks.describe(strength)


# --- unequal weights (statistic and exact p by hand) -------------------------------
# Cycle A: use [5], non-use [3, 3, 3] → diff 2,  weight 1·3/4 = 0.75
# Cycle B: use [4, 4], non-use [4, 2] → diff 1,  weight 2·2/4 = 1
# T = (0.75·2 + 1·1) / 1.75 = 2.5 / 1.75 = 10/7 ≈ 1.4286
# Null, cycle A (C(4,1) = 4): use = 5 → +2 (1 way); use = a 3 → 3 − 11/3 = −2/3 (3 ways)
# Null, cycle B (C(4,2) = 6): two 4s → +1 (3 ways); a 4 and the 2 → −1 (3 ways)
# T* = (0.75·a + b)/1.75:  (+2, +1) → 10/7 (3 ways); (+2, −1) → 2/7 (3);
#      (−2/3, +1) → 2/7 (9); (−2/3, −1) → −6/7 (9). Total 24.
# |T*| ≥ 10/7 only for the first: p = 3/24 = 1/8.

def test_weighted_statistic_and_exact_p_by_hand():
    blocks = [([5], [3, 3, 3]), ([4, 4], [4, 2])]
    assert whatworks.stratified_statistic(blocks) == pytest.approx(10 / 7)
    assert whatworks.stratified_p_value(blocks) == pytest.approx(1 / 8)


# --- wording -----------------------------------------------------------------------

def test_wording_is_associative(results):
    text = whatworks.describe(result(results, "follicular", "yoga"))
    assert text.startswith("In your data,") and "tended to be rated higher" in text
    assert "(5.0 vs 3.0 out of 5)" in text
    for causal in ("because", "boost", "hormone", "makes you", "improves"):
        assert causal not in text.lower()
