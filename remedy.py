"""Remedy Effectiveness Tracker (spec.md Feature 16) — local, no API.

Average relief rating per (symptom, remedy) pair. A pair with at least 3
logged instances is "ranked" (even if it's the only one for that
symptom); below that it's "not_enough_data" and gets no average at all,
so a couple of 5s can't look like a confident result.

Function contract pinned by tests/test_remedy.py (fixed, hand-verified).
"""
MIN_INSTANCES = 3


def normalize_remedy(text: str) -> str:
    """Lowercase, trim, and turn spaces into underscores, so "Heat Pad",
    " heat pad " and "heat_pad" are one remedy. Runs of whitespace become
    a single underscore."""
    normalized = "_".join(text.strip().lower().split())
    if not normalized:
        raise ValueError("Remedy can't be empty.")
    return normalized


def remedy_effectiveness(logs: list[dict]) -> dict[str, list[dict]]:
    """{symptom: [{"remedy", "avg_rating", "n", "status"}, ...]}.

    Ranked entries come first, highest average first; then
    not-enough-data entries (avg_rating None), most-logged first.
    """
    ratings: dict[tuple[str, str], list[int]] = {}
    for log in logs:
        key = (log["symptom"], normalize_remedy(log["remedy"]))
        ratings.setdefault(key, []).append(log["relief_rating"])

    result: dict[str, list[dict]] = {}
    for (symptom, remedy), values in ratings.items():
        enough = len(values) >= MIN_INSTANCES
        result.setdefault(symptom, []).append({
            "remedy": remedy,
            "avg_rating": sum(values) / len(values) if enough else None,
            "n": len(values),
            "status": "ranked" if enough else "not_enough_data",
        })
    for entries in result.values():
        entries.sort(key=lambda e: (
            e["status"] != "ranked",
            -(e["avg_rating"] or 0),
            -e["n"],
            e["remedy"],
        ))
    return result


def describe(entry: dict) -> str:
    """The plain line the app shows for one remedy."""
    name = entry["remedy"].replace("_", " ")
    if entry["status"] == "ranked":
        return f"{name}: {entry['avg_rating']:.1f} / 5 average relief ({entry['n']} times)"
    more = MIN_INSTANCES - entry["n"]
    return (
        f"{name}: logged {entry['n']} time{'s' if entry['n'] != 1 else ''} so far — "
        f"{more} more and Nova can show how well it tends to help."
    )
