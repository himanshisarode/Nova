"""Phase 10: the Level 2 migration is additive and keeps every existing row.

OLD_SCHEMA is a frozen copy of the pre-Level-2 schema (db.py and auth.py
at commit c9652f4). A database built with it, holding real-looking data,
is opened with today's code; every pre-existing row must be unchanged.
"""
import sqlite3
from datetime import date

import pytest

import db

OLD_SCHEMA = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL, display_name TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE daily_log (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date        TEXT NOT NULL CHECK (date(date) IS date),
    flow        TEXT CHECK (flow IN ('none', 'spotting', 'light', 'medium', 'heavy')),
    mood        INTEGER CHECK (mood BETWEEN 1 AND 5),
    poor_sleep  INTEGER NOT NULL DEFAULT 0 CHECK (poor_sleep IN (0, 1)),
    high_stress INTEGER NOT NULL DEFAULT 0 CHECK (high_stress IN (0, 1)),
    travel      INTEGER NOT NULL DEFAULT 0 CHECK (travel IN (0, 1)),
    PRIMARY KEY (user_id, date)
);
CREATE TABLE daily_symptom (
    user_id INTEGER NOT NULL, date TEXT NOT NULL, symptom TEXT NOT NULL,
    PRIMARY KEY (user_id, date, symptom),
    FOREIGN KEY (user_id, date) REFERENCES daily_log(user_id, date) ON DELETE CASCADE
);
CREATE TABLE partner_links (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    partner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    invite_code TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
    created_at TEXT NOT NULL, expires_at TEXT NOT NULL, accepted_at TEXT, revoked_at TEXT,
    CHECK (partner_user_id IS NULL OR partner_user_id != user_id)
);
CREATE TABLE remedy_log (
    id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date TEXT NOT NULL CHECK (date(date) IS date), symptom TEXT NOT NULL,
    remedy TEXT NOT NULL CHECK (remedy != '' AND remedy = lower(trim(remedy))),
    relief_rating INTEGER NOT NULL CHECK (relief_rating BETWEEN 1 AND 5)
);
CREATE TABLE cycle (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL CHECK (date(start_date) IS start_date),
    end_date TEXT NOT NULL CHECK (date(end_date) IS end_date),
    length INTEGER NOT NULL CHECK (length > 0),
    PRIMARY KEY (user_id, start_date)
);
"""
OLD_TABLES = ("users", "daily_log", "daily_symptom", "partner_links", "remedy_log", "cycle")


def snapshot(conn, table, columns=None):
    cols = ", ".join(columns) if columns else "*"
    return conn.execute(f"SELECT {cols} FROM {table} ORDER BY rowid").fetchall()


def columns(conn, table):
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


@pytest.fixture
def old_db(tmp_path):
    path = tmp_path / "old.db"
    conn = sqlite3.connect(path)
    conn.executescript(OLD_SCHEMA)
    with conn:
        conn.execute("INSERT INTO users VALUES (1, 'maya@example.com', '$2b$12$hash', 'Maya', '2026-01-01T00:00:00+00:00')")
        conn.execute("INSERT INTO users VALUES (2, 'bea@example.com', '$2b$12$hash2', 'Bea', '2026-01-02T00:00:00+00:00')")
        for day, flow, mood in [("2026-01-01", "heavy", 2), ("2026-01-02", "medium", None),
                                ("2026-01-29", "light", 4), ("2026-02-10", "none", 5)]:
            conn.execute("INSERT INTO daily_log VALUES (1, ?, ?, ?, 1, 0, 0)", (day, flow, mood))
        conn.execute("INSERT INTO daily_symptom VALUES (1, '2026-01-01', 'cramps')")
        conn.execute("INSERT INTO remedy_log VALUES (1, 1, '2026-01-01', 'cramps', 'heat_pad', 4)")
        conn.execute("INSERT INTO cycle VALUES (1, '2026-01-01', '2026-01-28', 28)")
        conn.execute("INSERT INTO partner_links VALUES (1, 1, 2, 'ABCDEFGH', 'accepted',"
                     " '2026-01-03T00:00:00+00:00', '2026-01-05T00:00:00+00:00', '2026-01-03T01:00:00+00:00', NULL)")
    before = {t: snapshot(conn, t) for t in OLD_TABLES}
    conn.close()
    return path, before


def test_old_database_migrates_and_keeps_every_row(old_db):
    path, before = old_db
    conn = db.connect(path)
    try:
        for table in OLD_TABLES:
            old_columns = [c for c in columns(conn, table) if c not in ("day_rating", "energy")]
            assert snapshot(conn, table, old_columns) == before[table], table
        assert {"day_rating", "energy"} <= set(columns(conn, "daily_log"))
        for table in ("daily_strategy", "user_settings", "phase_guide", "llm_usage"):
            assert columns(conn, table), table
        # Existing rows simply have no Level 2 values.
        assert conn.execute("SELECT COUNT(*) FROM daily_log WHERE day_rating IS NOT NULL OR energy IS NOT NULL").fetchone() == (0,)
        # And the old data still reads back through today's API.
        logs = db.get_logs(conn, 1)
        assert [(e.date, e.flow, e.mood) for e in logs][:2] == [
            (date(2026, 1, 1), "heavy", 2), (date(2026, 1, 2), "medium", None)]
        assert logs[0].symptoms == {"cramps"} and logs[0].day_rating is None and logs[0].strategies == set()
    finally:
        conn.close()


def test_migrate_twice_is_a_no_op(old_db):
    path, _ = old_db
    conn = db.connect(path)
    try:
        assert db.migrate(conn) == []
        assert columns(conn, "daily_log").count("day_rating") == 1
    finally:
        conn.close()


def test_migrate_reports_what_it_added(old_db):
    path, _ = old_db
    conn = sqlite3.connect(path)
    try:
        assert db.migrate(conn) == ["daily_log.day_rating", "daily_log.energy"]
    finally:
        conn.close()


def test_new_columns_keep_their_checks_after_migration(old_db):
    path, _ = old_db
    conn = db.connect(path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                conn.execute("UPDATE daily_log SET day_rating = 6 WHERE user_id = 1")
    finally:
        conn.close()
