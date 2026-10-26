"""
Hand-verified test fixture for remedy.py, per Nova_PLAN.md Phase 7.5.

Expected function signature (pin this down for whoever implements
remedy.py):

    remedy_effectiveness(logs: list[dict]) -> dict

    logs: [{"symptom": str, "remedy": str, "relief_rating": int}, ...]
    returns: {symptom: [{"remedy": str, "avg_rating": float, "n": int,
                          "status": "ranked" | "not_enough_data"}, ...]}
             sorted by avg_rating descending among "ranked" entries

The averages below were computed by hand and are hardcoded as the
expected answer, same reasoning as test_lifestyle_link.py -- this
checks the function's output against an independently-computed number,
not against its own internal formula.
"""
import pytest
from remedy import remedy_effectiveness


def _log(symptom, remedy, ratings):
    return [{"symptom": symptom, "remedy": remedy, "relief_rating": r} for r in ratings]


def test_averages_and_ranking_above_threshold():
    # heat_pad: 4, 5, 4, 4 -> 17/4 = 4.25 (n=4)
    # ibuprofen: 3, 3, 2 -> 8/3 ~= 2.667 (n=3)
    # Both >= the 3-instance minimum from SPEC.md -- both should be
    # ranked, heat_pad first since its average is higher.
    logs = (
        _log("cramps", "heat_pad", [4, 5, 4, 4])
        + _log("cramps", "ibuprofen", [3, 3, 2])
    )

    result = remedy_effectiveness(logs)
    cramps = {entry["remedy"]: entry for entry in result["cramps"]}

    assert cramps["heat_pad"]["status"] == "ranked"
    assert cramps["heat_pad"]["avg_rating"] == pytest.approx(4.25)
    assert cramps["heat_pad"]["n"] == 4

    assert cramps["ibuprofen"]["status"] == "ranked"
    assert cramps["ibuprofen"]["avg_rating"] == pytest.approx(8 / 3)
    assert cramps["ibuprofen"]["n"] == 3

    # heat_pad's higher average must sort it first
    ranked = [e for e in result["cramps"] if e["status"] == "ranked"]
    assert ranked[0]["remedy"] == "heat_pad"


def test_below_threshold_is_not_shown_as_confident_even_with_high_ratings():
    # walking: only 2 logged instances (5, 5) -- a tempting-looking
    # average, but below the 3-instance minimum. Must show
    # "not_enough_data", not a confident 5.0 -- this is the one most
    # likely to get silently skipped if the threshold check is buggy or
    # missing, since a passing test that only checks the above-threshold
    # case wouldn't catch it.
    logs = _log("cramps", "walking", [5, 5])

    result = remedy_effectiveness(logs)
    walking = next(e for e in result["cramps"] if e["remedy"] == "walking")

    assert walking["status"] == "not_enough_data"
    assert walking["n"] == 2