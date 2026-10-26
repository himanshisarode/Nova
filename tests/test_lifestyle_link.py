"""
Hand-verified test fixture for lifestyle_link.py, per Nova_PLAN.md Phase 7.5.

Expected function signature (pin this down for whoever implements
lifestyle_link.py):

    check_lifestyle_link(cycles: list[dict], tag: str) -> dict

    cycles: [{"length": int, "tags": list[str]}, ...]
    returns either
        {"status": "not_enough_data"}
    or
        {"status": "result", "with_tag_mean": float, "without_tag_mean": float,
         "significant": bool}

The numbers below were computed by hand first (see the chat message this
file came from) and are hardcoded here as the expected answer — the test
does NOT re-derive them from scipy, it checks the function's output
against an independently-computed known-correct answer. That's the whole
point: this test would still catch a bug even if lifestyle_link.py used
the exact same (buggy) formula internally.
"""
import pytest
from lifestyle_link import check_lifestyle_link


def _cycles(with_tag_lengths, without_tag_lengths, tag):
    cycles = [{"length": L, "tags": [tag]} for L in with_tag_lengths]
    cycles += [{"length": L, "tags": []} for L in without_tag_lengths]
    return cycles


def test_planted_link_is_detected():
    # With high_stress: 31, 33, 30, 32 -> mean 31.5
    # Without:          28, 27, 29, 28 -> mean 28.0
    # By hand: Welch's t ~= 4.58, df ~= 5, clears the critical t (~2.57
    # at df=5, alpha=0.05) by a wide margin -> must be significant.
    cycles = _cycles([31, 33, 30, 32], [28, 27, 29, 28], "high_stress")

    result = check_lifestyle_link(cycles, "high_stress")

    assert result["status"] == "result"
    assert result["with_tag_mean"] == pytest.approx(31.5)
    assert result["without_tag_mean"] == pytest.approx(28.0)
    assert result["significant"] is True


def test_no_real_link_is_not_falsely_flagged():
    # Negative control: travel-tagged and non-travel cycles have the
    # identical mean (28.0 vs 28.0) -- there is nothing here to find,
    # and the function must not report significance just because it was
    # asked to look for one.
    cycles = _cycles([29, 27, 30, 26], [28, 29, 27, 28], "travel")

    result = check_lifestyle_link(cycles, "travel")

    assert result["status"] == "result"
    assert result["with_tag_mean"] == pytest.approx(28.0)
    assert result["without_tag_mean"] == pytest.approx(28.0)
    assert result["significant"] is False


def test_insufficient_data_below_three_per_group():
    # Only 2 cycles tagged "high_stress" -- below the 3-per-group
    # minimum from SPEC.md. Must refuse to report a result at all,
    # regardless of how the numbers look.
    cycles = _cycles([31, 33], [28, 27, 29, 28, 30], "high_stress")

    result = check_lifestyle_link(cycles, "high_stress")

    assert result["status"] == "not_enough_data"