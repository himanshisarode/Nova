"""Phase 10: the "what works for me" log and settings in db.py (Feature 18)."""
from datetime import date

import pytest

import auth
import db
import predict


@pytest.fixture
def conn(tmp_path):
    conn = db.connect(tmp_path / "nova.db")
    yield conn
    conn.close()


@pytest.fixture
def user(conn):
    return auth.signup(conn, "maya@example.com", "password-maya-1", "Maya").id


DAY = date(2026, 3, 4)


def test_ratings_and_strategies_round_trip(conn, user):
    db.save_log(conn, user, db.LogEntry(DAY, flow="none", day_rating=4, energy=2,
                                        strategies={"walk", "early_night"}))
    entry = db.get_log(conn, user, DAY)
    assert (entry.day_rating, entry.energy, entry.strategies) == (4, 2, {"walk", "early_night"})


def test_relogging_a_day_replaces_its_strategies(conn, user):
    db.save_log(conn, user, db.LogEntry(DAY, strategies={"walk", "yoga"}, day_rating=3))
    db.save_log(conn, user, db.LogEntry(DAY, strategies={"strength"}, day_rating=5))
    entry = db.get_log(conn, user, DAY)
    assert entry.strategies == {"strength"} and entry.day_rating == 5


def test_everything_level2_is_optional(conn, user):
    db.save_log(conn, user, db.LogEntry(DAY, flow="light"))
    entry = db.get_log(conn, user, DAY)
    assert entry.day_rating is None and entry.energy is None and entry.strategies == set()


@pytest.mark.parametrize("kwargs", [
    {"day_rating": 0}, {"day_rating": 6}, {"energy": 0}, {"energy": 6},
    {"strategies": {"calorie_counting"}},
])
def test_out_of_range_or_unknown_values_are_refused(kwargs):
    with pytest.raises(ValueError):
        db.LogEntry(DAY, **kwargs)


def test_database_refuses_unknown_strategies_too(conn, user):
    db.save_log(conn, user, db.LogEntry(DAY))
    with pytest.raises(Exception):
        with conn:
            conn.execute("INSERT INTO daily_strategy VALUES (?, ?, 'diet')", (user, DAY.isoformat()))


def test_strategy_list_has_no_diet_or_weight_items():
    assert len(db.STRATEGIES) == 10
    for banned in ("calorie", "weight", "diet", "food", "fast", "meal"):
        assert not any(banned in s for s in db.STRATEGIES)


def test_save_logs_bulk_matches_save_log(conn, user):
    entries = [db.LogEntry(date(2026, 1, k), flow="heavy" if k in (1, 29) else "none",
                           day_rating=3, strategies={"walk"}) for k in range(1, 31)]
    db.save_logs(conn, user, entries)
    assert db.get_logs(conn, user) == entries
    assert [c.length for c in db.get_cycles(conn, user)] == [28]


# --- settings -------------------------------------------------------------------

def test_settings_default_to_off(conn, user):
    s = db.get_settings(conn, user)
    assert s == db.Settings()
    assert s.luteal_days is None and not s.phase_guide_opt_in and not s.week_fit_opt_in


def test_update_settings_changes_only_what_is_given(conn, user):
    db.update_settings(conn, user, luteal_days=12)
    s = db.update_settings(conn, user, week_fit_opt_in=True)
    assert s.luteal_days == 12 and s.week_fit_opt_in and not s.phase_guide_opt_in
    s = db.update_settings(conn, user, week_fit_opt_in=False, luteal_days=None)
    assert s == db.Settings()


@pytest.mark.parametrize("bad", [9, 18])
def test_luteal_days_range(conn, user, bad):
    with pytest.raises(ValueError):
        db.update_settings(conn, user, luteal_days=bad)


def test_unknown_setting_is_refused(conn, user):
    with pytest.raises(ValueError):
        db.update_settings(conn, user, password_hash="x")


def test_luteal_setting_moves_the_fertile_window():
    p = predict.SimplePrediction(next_start=date(2026, 5, 1), mean_length=29, n_cycles=3)
    default = predict.fertile_window(p)
    assert default == predict.fertile_window(p, luteal_days=None)
    assert default.ovulation_earliest == date(2026, 4, 17)  # May 1 − 14
    assert predict.fertile_window(p, luteal_days=12).ovulation_earliest == date(2026, 4, 19)


# --- delete-all covers Level 2 data ---------------------------------------------

def test_delete_account_removes_level2_rows(conn, user):
    other = auth.signup(conn, "bea@example.com", "password-bea-12", "Bea").id
    for u in (user, other):
        db.save_log(conn, u, db.LogEntry(DAY, day_rating=4, strategies={"yoga"}))
        db.update_settings(conn, u, luteal_days=13, phase_guide_opt_in=True)
        conn.execute("INSERT INTO phase_guide VALUES (?, '2026-01-01', '{}', 'now')", (u,))
        conn.execute("INSERT INTO llm_usage VALUES (?, '2026-03-04', 'phase_guide', 1)", (u,))
    conn.commit()
    db.delete_account(conn, user, "maya@example.com")
    for table in ("daily_strategy", "user_settings", "phase_guide", "llm_usage"):
        rows = conn.execute(f"SELECT user_id FROM {table}").fetchall()
        assert rows == [(other,)], table
