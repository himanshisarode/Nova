"""Phase 11: the by-phase analysis on simulated people, and its plumbing.

The hand-checked numbers live in test_whatworks_fixture.py (fixed).
This file checks behaviour at scale and the glue around it.
"""
import ast
from datetime import date, timedelta
from pathlib import Path

import pytest

import db
import simulate
import whatworks

ROOT = Path(__file__).parent.parent
PLANTED = {("follicular", "strength"): 1.0, ("luteal", "early_night"): 1.0}
PEOPLE = 40
N_CYCLES = 8  # a little past the gate's 4-cycle minimum, ~8 months


@pytest.fixture(scope="module")
def simulated():
    found = {k: 0 for k in PLANTED}
    null_with_any = 0
    for seed in range(PEOPLE):
        h = simulate.simulate_history(seed, n_cycles=N_CYCLES, irregular_rate=0.0)
        res = whatworks.analyse(whatworks.rated_days(h.starts, simulate.with_strategies(h, seed, PLANTED)))
        good = {(r.bucket, r.strategy) for r in res if r.verdict == "tends_to_go_well"}
        for k in PLANTED:
            found[k] += k in good
        res0 = whatworks.analyse(whatworks.rated_days(h.starts, simulate.with_strategies(h, seed + 1000)))
        null_with_any += any(r.verdict == "tends_to_go_well" for r in res0)
    return found, null_with_any


def test_planted_effects_are_found_in_at_least_80_percent(simulated):
    found, _ = simulated
    for key, n in found.items():
        assert n / PEOPLE >= 0.80, (key, n / PEOPLE)


def test_people_with_no_effect_rarely_get_a_finding(simulated):
    _, null_with_any = simulated
    assert null_with_any / PEOPLE <= 0.10


def test_level2_simulation_leaves_existing_numbers_unchanged():
    # with_strategies uses its own random stream: the base history is the same.
    h = simulate.simulate_history(7, n_cycles=6)
    again = simulate.simulate_history(7, n_cycles=6)
    simulate.with_strategies(h, 7, PLANTED)
    assert h == again
    logs = simulate.with_strategies(h, 7, PLANTED)
    assert [(e.date, e.flow, e.mood) for e in logs] == [(e.date, e.flow, e.mood) for e in h.logs]


def test_rated_days_uses_completed_cycles_only_and_skips_unrated_days():
    h = simulate.simulate_history(3, n_cycles=4)
    logs = simulate.with_strategies(h, 3, PLANTED)
    days = whatworks.rated_days(h.starts, logs)
    assert all(h.starts[0] <= d.day < h.starts[-1] for d in days)
    assert len(days) == sum(1 for e in logs if e.day_rating is not None and e.date < h.starts[-1])
    assert {d.bucket for d in days} == {"period", "follicular", "luteal"}
    assert {d.cycle for d in days} == {0, 1, 2, 3}


def test_a_brand_new_user_gets_not_enough_data_everywhere():
    results = whatworks.analyse([])
    assert len(results) == 3 * len(db.STRATEGIES)
    assert all(r.verdict == "not_enough_data" for r in results)


def test_monte_carlo_path_is_reproducible():
    # Big enough that exact enumeration is skipped (C(20,10)^2 > 20,000).
    blocks = [([5, 4, 4, 5, 3, 4, 5, 4, 4, 5], [3, 3, 4, 2, 3, 3, 4, 3, 2, 3])] * 2
    p1 = whatworks.stratified_p_value(blocks)
    assert p1 == whatworks.stratified_p_value(blocks)
    assert 0 < p1 < 0.01


def test_benjamini_hochberg_known_values():
    # Textbook example: p = [0.01, 0.04, 0.03, 0.20], m = 4.
    # Sorted 0.01, 0.03, 0.04, 0.20 → raw 0.04, 0.06, 0.0533, 0.20 → monotone
    # from the top: 0.20, 0.0533, 0.0533, 0.04.
    q = whatworks.benjamini_hochberg([0.01, 0.04, 0.03, 0.20])
    assert q == pytest.approx([0.04, 0.16 / 3, 0.16 / 3, 0.20])


def test_whatworks_imports_nothing_network_capable():
    tree = ast.parse((ROOT / "whatworks.py").read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert not imported & {"socket", "urllib", "http", "requests", "httpx", "httpx2", "anthropic", "llm"}
