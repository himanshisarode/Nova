"""Phase 3: the simulator produces what it claims to."""
import numpy as np

import db
import simulate


def test_same_seed_same_history():
    a, b = simulate.simulate_history(7), simulate.simulate_history(7)
    assert a.lengths == b.lengths and a.irregular == b.irregular and a.logs == b.logs


def test_logs_reproduce_the_simulated_cycles_through_the_real_period_rule():
    # The daily logs must decode back to exactly the cycles the simulator
    # intended, via db's period rule (spotting days included).
    for seed in range(50):
        h = simulate.simulate_history(seed, n_cycles=12, irregular_rate=0.3)
        bleeding = [e.date for e in h.logs if e.flow in db.BLEEDING_FLOWS]
        starts = db.period_starts(bleeding)
        assert starts == h.starts
        assert [c.length for c in db.cycles_from_starts(starts)] == h.lengths


def test_irregular_share_matches_the_requested_rate():
    flags = []
    for seed in range(400):
        flags += simulate.simulate_history(seed, n_cycles=12).irregular
    assert 0.13 <= np.mean(flags) <= 0.17


def test_lengths_never_below_minimum():
    lengths = []
    for seed in range(400):
        lengths += simulate.simulate_history(seed, n_cycles=12, irregular_rate=0.5).lengths
    assert min(lengths) >= simulate.MIN_LENGTH


def test_stress_link_plants_more_stress_in_irregular_cycles():
    h = simulate.simulate_history(3, n_cycles=40, irregular_rate=0.3, stress_link=True)
    by_day = {e.date: e for e in h.logs}
    rates = {True: [], False: []}
    for start, length, irregular in zip(h.starts, h.lengths, h.irregular):
        days = [by_day[start + np.timedelta64(k, "D").astype(object)] for k in range(length)]
        rates[irregular].append(np.mean([d.high_stress for d in days]))
    assert np.mean(rates[True]) > 3 * np.mean(rates[False])
