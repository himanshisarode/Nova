"""Lifestyle-Link Finder (spec.md Feature 15) — local statistics, no API.

For one lifestyle tag, split completed cycles into "tag logged on any
day of the cycle" vs "not", and compare average cycle length with a
two-sided Welch's t-test at alpha = 0.05. Below 3 cycles in either group
there is no result at all, only "not enough data yet".

Function contract pinned by tests/test_lifestyle_link.py (fixed,
hand-verified — don't change the signature or return shape).
"""
import math
from datetime import timedelta

from scipy import stats

from db import LIFESTYLE_TAGS, Cycle, LogEntry

MIN_PER_GROUP = 3
ALPHA = 0.05
TAG_PHRASES = {"poor_sleep": "poor sleep", "high_stress": "high stress", "travel": "travel"}


def cycles_with_tags(cycles: list[Cycle], logs: list[LogEntry]) -> list[dict]:
    """[{"length", "tags"}] per completed cycle; a tag counts if it was
    logged on any day within the cycle."""
    by_day = {e.date: e for e in logs}
    out = []
    for cycle in cycles:
        tags: set[str] = set()
        for k in range(cycle.length):
            entry = by_day.get(cycle.start + timedelta(days=k))
            if entry is not None:
                tags |= entry.tags
        out.append({"length": cycle.length, "tags": sorted(tags)})
    return out


def check_lifestyle_link(cycles: list[dict], tag: str) -> dict:
    """Compare cycle length with vs without `tag`.

    Returns {"status": "not_enough_data", "n_with", "n_without"} or
    {"status": "result", "with_tag_mean", "without_tag_mean",
     "significant", "p_value", "n_with", "n_without"}.
    """
    with_tag = [c["length"] for c in cycles if tag in c["tags"]]
    without_tag = [c["length"] for c in cycles if tag not in c["tags"]]
    counts = {"n_with": len(with_tag), "n_without": len(without_tag)}
    if len(with_tag) < MIN_PER_GROUP or len(without_tag) < MIN_PER_GROUP:
        return {"status": "not_enough_data", **counts}

    if len(set(with_tag)) == 1 and len(set(without_tag)) == 1:
        # Zero spread in both groups: Welch's t is undefined. Treated as no
        # evidence of a link rather than guessing either way.
        p_value = math.nan
    else:
        p_value = float(stats.ttest_ind(with_tag, without_tag, equal_var=False).pvalue)
    significant = not math.isnan(p_value) and p_value < ALPHA
    return {
        "status": "result",
        "with_tag_mean": sum(with_tag) / len(with_tag),
        "without_tag_mean": sum(without_tag) / len(without_tag),
        "significant": significant,
        "p_value": p_value,
        **counts,
    }


def describe(result: dict, tag: str) -> str:
    """The plain sentence the app shows for a result."""
    phrase = TAG_PHRASES.get(tag, tag.replace("_", " "))
    if result["status"] == "not_enough_data":
        return (
            f"Still gathering cycles with and without {phrase} logged — Nova needs at "
            f"least {MIN_PER_GROUP} of each before it can look for a link."
        )
    if not result["significant"]:
        return f"No significant link found yet between {phrase} and your cycle length."
    diff = result["with_tag_mean"] - result["without_tag_mean"]
    direction = "longer" if diff > 0 else "shorter"
    return (
        f"Cycles with {phrase} logged ran {abs(diff):.1f} days {direction} on average "
        f"({result['with_tag_mean']:.1f} vs {result['without_tag_mean']:.1f} days)."
    )


def all_links(cycles: list[dict]) -> dict[str, dict]:
    """Results for every lifestyle tag the app logs."""
    return {tag: check_lifestyle_link(cycles, tag) for tag in LIFESTYLE_TAGS}
