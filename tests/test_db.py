"""Phase 2: per-user storage, persistence, and the cycle derivation rule."""
import sqlite3
from datetime import date, timedelta

import pytest

import auth
import db

D = date.fromisoformat


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "nova.db"


@pytest.fixture
def conn(db_path):
    conn = db.connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def users(conn):
    a = auth.signup(conn, "a@example.com", "password-a-123", "A")
    b = auth.signup(conn, "b@example.com", "password-b-123", "B")
    return a.id, b.id


def log_period(conn, user_id, first_day, days=5, flow="medium"):
    for i in range(days):
        db.save_log(conn, user_id, db.LogEntry(first_day + timedelta(days=i), flow=flow))


# --- persistence and per-user separation --------------------------------------

def test_logs_persist_across_reopening_the_file(db_path):
    conn = db.connect(db_path)
    user = auth.signup(conn, "a@example.com", "password-a-123", "A")
    entry = db.LogEntry(
        D("2026-10-01"), flow="heavy", mood=2,
        symptoms=frozenset({"cramps", "fatigue"}), high_stress=True,
    )
    db.save_log(conn, user.id, entry)
    conn.close()

    reopened = db.connect(db_path)
    try:
        assert db.get_log(reopened, user.id, D("2026-10-01")) == entry
    finally:
        reopened.close()


def test_two_users_same_date_stay_separate(conn, users):
    a, b = users
    day = D("2026-10-01")
    db.save_log(conn, a, db.LogEntry(day, flow="heavy", symptoms=frozenset({"cramps"})))
    db.save_log(conn, b, db.LogEntry(day, flow="none", mood=5))

    assert db.get_log(conn, a, day) == db.LogEntry(day, flow="heavy", symptoms=frozenset({"cramps"}))
    assert db.get_log(conn, b, day) == db.LogEntry(day, flow="none", mood=5)


def test_one_users_edits_and_deletes_dont_touch_the_other(conn, users):
    a, b = users
    day = D("2026-10-01")
    db.save_log(conn, a, db.LogEntry(day, flow="light"))
    db.save_log(conn, b, db.LogEntry(day, flow="light", symptoms=frozenset({"acne"})))

    db.save_log(conn, a, db.LogEntry(day, flow="heavy"))
    db.delete_log(conn, a, day)

    assert db.get_logs(conn, a) == []
    assert db.get_logs(conn, b) == [db.LogEntry(day, flow="light", symptoms=frozenset({"acne"}))]


def test_cycles_are_per_user(conn, users):
    a, b = users
    for start in (D("2026-01-01"), D("2026-01-29"), D("2026-02-27")):
        log_period(conn, a, start)
    log_period(conn, b, D("2026-01-10"))

    assert [c.length for c in db.get_cycles(conn, a)] == [28, 29]
    assert db.get_cycles(conn, b) == []


def test_logging_for_a_nonexistent_user_fails(conn):
    with pytest.raises(sqlite3.IntegrityError):
        db.save_log(conn, 999, db.LogEntry(D("2026-10-01"), flow="light"))


# --- saving / replacing -------------------------------------------------------

def test_saving_same_date_replaces_the_whole_day(conn, users):
    a, _ = users
    day = D("2026-10-01")
    db.save_log(conn, a, db.LogEntry(day, flow="heavy", mood=1,
                                     symptoms=frozenset({"cramps", "nausea"}), travel=True))
    db.save_log(conn, a, db.LogEntry(day, flow="light", symptoms=frozenset({"fatigue"})))

    assert db.get_logs(conn, a) == [db.LogEntry(day, flow="light", symptoms=frozenset({"fatigue"}))]


def test_past_days_can_be_logged(conn, users):
    a, _ = users
    db.save_log(conn, a, db.LogEntry(D("2026-10-05")))
    db.save_log(conn, a, db.LogEntry(D("2025-12-31"), mood=3))
    assert [e.date for e in db.get_logs(conn, a)] == [D("2025-12-31"), D("2026-10-05")]


def test_get_logs_date_range_is_inclusive(conn, users):
    a, _ = users
    for d in ("2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"):
        db.save_log(conn, a, db.LogEntry(D(d)))
    got = db.get_logs(conn, a, D("2026-10-02"), D("2026-10-03"))
    assert [e.date for e in got] == [D("2026-10-02"), D("2026-10-03")]


def test_lifestyle_tags_round_trip(conn, users):
    a, _ = users
    entry = db.LogEntry(D("2026-10-01"), poor_sleep=True, travel=True)
    db.save_log(conn, a, entry)
    assert db.get_log(conn, a, D("2026-10-01")).tags == {"poor_sleep", "travel"}


# --- validation ---------------------------------------------------------------

@pytest.mark.parametrize(
    "kwargs",
    [{"flow": "gushing"}, {"mood": 0}, {"mood": 6}, {"symptoms": frozenset({"sneezing"})}],
)
def test_invalid_entries_rejected(kwargs):
    with pytest.raises(ValueError):
        db.LogEntry(D("2026-10-01"), **kwargs)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO daily_log (user_id, date, flow) VALUES (1, '2026-10-01', 'gushing')",
        "INSERT INTO daily_log (user_id, date, mood) VALUES (1, '2026-10-01', 9)",
        "INSERT INTO daily_log (user_id, date) VALUES (1, '2026-13-45')",
    ],
)
def test_database_itself_rejects_bad_values(conn, users, sql):
    # The CHECK constraints are a second line of defense if something
    # ever writes without going through LogEntry.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql)


# --- period starts and cycles (expected values worked out by hand) ------------

def test_period_starts_basic():
    # Bleeding Jan 1–5, Jan 29–Feb 2, Feb 27–Mar 3.
    bleeding = []
    for start in (D("2026-01-01"), D("2026-01-29"), D("2026-02-27")):
        bleeding += [start + timedelta(days=i) for i in range(5)]
    assert db.period_starts(bleeding) == [D("2026-01-01"), D("2026-01-29"), D("2026-02-27")]


def test_mid_period_pause_is_the_same_period(conn, users):
    # The exact scenario from spec.md's period rule: bleeding day 1,
    # nothing logged days 2–3, light flow day 4 -> one period, not two.
    a, _ = users
    db.save_log(conn, a, db.LogEntry(D("2026-01-01"), flow="heavy"))
    db.save_log(conn, a, db.LogEntry(D("2026-01-04"), flow="light"))
    assert db.get_period_starts(conn, a) == [D("2026-01-01")]
    assert db.get_cycles(conn, a) == []


def test_six_non_bleeding_days_is_still_the_same_period():
    # Bleeding Jan 1, non-bleeding Jan 2–7 (6 days), bleeding Jan 8.
    assert db.period_starts([D("2026-01-01"), D("2026-01-08")]) == [D("2026-01-01")]


def test_seven_non_bleeding_days_starts_a_new_period():
    # Bleeding Jan 1, non-bleeding Jan 2–8 (7 days), bleeding Jan 9.
    assert db.period_starts([D("2026-01-01"), D("2026-01-09")]) == [D("2026-01-01"), D("2026-01-09")]


def test_spotting_in_the_gap_counts_as_non_bleeding(conn, users):
    # Spotting every day Jan 2–8 doesn't bridge the gap: Jan 9 is a new period.
    a, _ = users
    db.save_log(conn, a, db.LogEntry(D("2026-01-01"), flow="medium"))
    for day in range(2, 9):
        db.save_log(conn, a, db.LogEntry(date(2026, 1, day), flow="spotting"))
    db.save_log(conn, a, db.LogEntry(D("2026-01-09"), flow="light"))
    assert db.get_period_starts(conn, a) == [D("2026-01-01"), D("2026-01-09")]


def test_cycle_lengths_and_open_cycle_excluded():
    starts = [D("2026-01-01"), D("2026-01-29"), D("2026-02-27")]
    # Jan 1 -> Jan 29 is 28 days; Jan 29 -> Feb 27 is 29 days (Feb 2026 has
    # 28 days: 2 days left in Jan + 27 in Feb). The cycle starting Feb 27 is
    # still open, so it isn't counted.
    assert db.cycles_from_starts(starts) == [
        db.Cycle(D("2026-01-01"), D("2026-01-28"), 28),
        db.Cycle(D("2026-01-29"), D("2026-02-26"), 29),
    ]


def test_spotting_never_starts_a_period(conn, users):
    a, _ = users
    log_period(conn, a, D("2026-01-01"))
    # Spotting Jan 27–28, then real bleeding from Jan 29: the start is Jan 29,
    # not the spotting day.
    db.save_log(conn, a, db.LogEntry(D("2026-01-27"), flow="spotting"))
    db.save_log(conn, a, db.LogEntry(D("2026-01-28"), flow="spotting"))
    log_period(conn, a, D("2026-01-29"))
    assert db.get_period_starts(conn, a) == [D("2026-01-01"), D("2026-01-29")]
    assert db.get_cycles(conn, a) == [db.Cycle(D("2026-01-01"), D("2026-01-28"), 28)]


def test_unlogged_days_count_as_non_bleeding(conn, users):
    a, _ = users
    # Only two days logged at all, 4 weeks apart.
    db.save_log(conn, a, db.LogEntry(D("2026-03-01"), flow="light"))
    db.save_log(conn, a, db.LogEntry(D("2026-03-29"), flow="light"))
    assert [c.length for c in db.get_cycles(conn, a)] == [28]


def test_editing_a_log_rebuilds_cycles(conn, users):
    a, _ = users
    log_period(conn, a, D("2026-01-01"))
    log_period(conn, a, D("2026-01-29"), days=1)
    assert [c.length for c in db.get_cycles(conn, a)] == [28]

    # The Jan 29 bleed turns out to have been a mistake.
    db.save_log(conn, a, db.LogEntry(D("2026-01-29"), flow="none"))
    assert db.get_cycles(conn, a) == []

    db.save_log(conn, a, db.LogEntry(D("2026-01-29"), flow="heavy"))
    db.delete_log(conn, a, D("2026-01-29"))
    assert db.get_cycles(conn, a) == []


# --- where the database lives ---------------------------------------------------

def test_connect_without_a_path_honours_nova_db_path(tmp_path, monkeypatch):
    # Regression: db.connect() used to ignore NOVA_DB_PATH, so code run
    # inside the container (e.g. `docker compose exec`) wrote to the
    # container's own disk instead of the /data volume.
    target = tmp_path / "volume" / "nova.db"
    monkeypatch.setenv("NOVA_DB_PATH", str(target))
    conn = db.connect()
    auth.signup(conn, "a@example.com", "password-a-123", "A")
    conn.close()
    assert target.is_file()
    assert db.db_path() == target


def test_default_location_without_the_variable(monkeypatch):
    monkeypatch.delenv("NOVA_DB_PATH", raising=False)
    assert db.db_path() == db.DEFAULT_DB_PATH
