"""SQLite storage for Nova: per-user daily logs, their symptoms, and cycles.

Every table carries a user_id, and every function here takes one — there
is no way to read or write a log without saying whose it is.

Cycles are derived data: each write that changes a user's logs rebuilds
that user's `cycle` rows in the same transaction, using the period-start
rule in spec.md's Data section, so the table can't drift out of sync.
"""
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import auth
from remedy import normalize_remedy

DEFAULT_DB_PATH = Path(__file__).parent / "data" / "nova.db"


def db_path() -> Path:
    """Where the database lives: NOVA_DB_PATH if set (Docker points it at
    the /data volume), else data/nova.db. Read at call time, so every
    caller — the app, scripts, `docker compose exec` — agrees."""
    return Path(os.environ.get("NOVA_DB_PATH") or DEFAULT_DB_PATH)

# None (not recorded) is also allowed. "spotting" is logged but never
# counts as bleeding, so it can't start a period.
FLOW_LEVELS: tuple[str, ...] = ("none", "spotting", "light", "medium", "heavy")
BLEEDING_FLOWS: tuple[str, ...] = ("light", "medium", "heavy")
SYMPTOMS: tuple[str, ...] = (
    "cramps", "headache", "bloating", "fatigue", "acne",
    "breast_tenderness", "back_pain", "nausea", "mood_swings", "insomnia",
)
LIFESTYLE_TAGS: tuple[str, ...] = ("poor_sleep", "high_stress", "travel")
MOOD_RANGE = (1, 5)
# Level 2 "what works for me" log (spec.md Data, Feature 18). Fixed list:
# things a person does, nothing about food, calories or weight.
STRATEGIES: tuple[str, ...] = (
    "walk", "yoga", "strength", "cardio", "rest_day",
    "deep_focus_work", "light_admin", "social_plans", "early_night", "journaling",
)
RATING_RANGE = (1, 5)  # day_rating ("how did today go") and energy
LUTEAL_DAYS_RANGE = (10, 17)
# A bleeding day starts a new period only if the PERIOD_GAP_DAYS days
# before it were all non-bleeding (no log, no flow, or spotting); shorter
# pauses are the same period (spec.md Data, "Period rule").
PERIOD_GAP_DAYS = 7


def _sql_list(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


SCHEMA = f"""
CREATE TABLE IF NOT EXISTS daily_log (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date        TEXT NOT NULL CHECK (date(date) IS date),
    flow        TEXT CHECK (flow IN ({_sql_list(FLOW_LEVELS)})),
    mood        INTEGER CHECK (mood BETWEEN {MOOD_RANGE[0]} AND {MOOD_RANGE[1]}),
    poor_sleep  INTEGER NOT NULL DEFAULT 0 CHECK (poor_sleep IN (0, 1)),
    high_stress INTEGER NOT NULL DEFAULT 0 CHECK (high_stress IN (0, 1)),
    travel      INTEGER NOT NULL DEFAULT 0 CHECK (travel IN (0, 1)),
    PRIMARY KEY (user_id, date)
);
CREATE TABLE IF NOT EXISTS daily_symptom (
    user_id INTEGER NOT NULL,
    date    TEXT NOT NULL,
    symptom TEXT NOT NULL CHECK (symptom IN ({_sql_list(SYMPTOMS)})),
    PRIMARY KEY (user_id, date, symptom),
    FOREIGN KEY (user_id, date) REFERENCES daily_log(user_id, date) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS partner_links (
    id              INTEGER PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    partner_user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    invite_code     TEXT NOT NULL UNIQUE,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
    created_at      TEXT NOT NULL,
    expires_at      TEXT NOT NULL,
    accepted_at     TEXT,
    revoked_at      TEXT,
    CHECK (partner_user_id IS NULL OR partner_user_id != user_id)
);
CREATE TABLE IF NOT EXISTS remedy_log (
    id            INTEGER PRIMARY KEY,
    user_id       INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date          TEXT NOT NULL CHECK (date(date) IS date),
    symptom       TEXT NOT NULL CHECK (symptom IN ({_sql_list(SYMPTOMS)})),
    remedy        TEXT NOT NULL CHECK (remedy != '' AND remedy = lower(trim(remedy))),
    relief_rating INTEGER NOT NULL CHECK (relief_rating BETWEEN 1 AND 5)
);
CREATE TABLE IF NOT EXISTS cycle (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL CHECK (date(start_date) IS start_date),
    end_date   TEXT NOT NULL CHECK (date(end_date) IS end_date),
    length     INTEGER NOT NULL CHECK (length > 0),
    PRIMARY KEY (user_id, start_date)
);
CREATE TABLE IF NOT EXISTS daily_strategy (
    user_id  INTEGER NOT NULL,
    date     TEXT NOT NULL,
    strategy TEXT NOT NULL CHECK (strategy IN ({_sql_list(STRATEGIES)})),
    PRIMARY KEY (user_id, date, strategy),
    FOREIGN KEY (user_id, date) REFERENCES daily_log(user_id, date) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS user_settings (
    user_id                INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    luteal_days            INTEGER CHECK (luteal_days BETWEEN {LUTEAL_DAYS_RANGE[0]} AND {LUTEAL_DAYS_RANGE[1]}),
    hormonal_contraception INTEGER CHECK (hormonal_contraception IN (0, 1)),
    phase_guide_opt_in     INTEGER CHECK (phase_guide_opt_in IN (0, 1)),
    week_fit_opt_in        INTEGER CHECK (week_fit_opt_in IN (0, 1)),
    is_demo                INTEGER CHECK (is_demo IN (0, 1))
);
CREATE TABLE IF NOT EXISTS phase_guide (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cycle_start TEXT NOT NULL,
    guide_json  TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, cycle_start)
);
CREATE TABLE IF NOT EXISTS llm_usage (
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day       TEXT NOT NULL,
    call_type TEXT NOT NULL,
    count     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, day, call_type)
);
"""

# Level 2 columns on existing tables. Added by migrate() — never part of a
# CREATE TABLE, so new and upgraded databases take exactly the same path.
# All nullable: existing rows simply have no value.
NEW_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("daily_log", "day_rating",
     f"INTEGER CHECK (day_rating BETWEEN {RATING_RANGE[0]} AND {RATING_RANGE[1]})"),
    ("daily_log", "energy",
     f"INTEGER CHECK (energy BETWEEN {RATING_RANGE[0]} AND {RATING_RANGE[1]})"),
)


@dataclass(frozen=True)
class LogEntry:
    """One day's log, exactly as the user entered it."""

    date: date
    flow: str | None = None
    mood: int | None = None
    symptoms: frozenset[str] = field(default_factory=frozenset)
    poor_sleep: bool = False
    high_stress: bool = False
    travel: bool = False
    # Level 2 "what works for me" (all optional; appended so positional
    # construction of the fields above is unchanged).
    day_rating: int | None = None
    energy: int | None = None
    strategies: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        if self.flow is not None and self.flow not in FLOW_LEVELS:
            raise ValueError(f"flow must be one of {FLOW_LEVELS} or None, got {self.flow!r}")
        if self.mood is not None and not MOOD_RANGE[0] <= self.mood <= MOOD_RANGE[1]:
            raise ValueError(f"mood must be between {MOOD_RANGE[0]} and {MOOD_RANGE[1]}, got {self.mood}")
        unknown = set(self.symptoms) - set(SYMPTOMS)
        if unknown:
            raise ValueError(f"unknown symptoms {sorted(unknown)}; allowed: {SYMPTOMS}")
        object.__setattr__(self, "symptoms", frozenset(self.symptoms))
        for name in ("day_rating", "energy"):
            value = getattr(self, name)
            if value is not None and not RATING_RANGE[0] <= value <= RATING_RANGE[1]:
                raise ValueError(f"{name} must be between {RATING_RANGE[0]} and {RATING_RANGE[1]}, got {value}")
        unknown = set(self.strategies) - set(STRATEGIES)
        if unknown:
            raise ValueError(f"unknown strategies {sorted(unknown)}; allowed: {STRATEGIES}")
        object.__setattr__(self, "strategies", frozenset(self.strategies))

    @property
    def tags(self) -> frozenset[str]:
        """The lifestyle tags set on this day."""
        return frozenset(t for t in LIFESTYLE_TAGS if getattr(self, t))


@dataclass(frozen=True)
class Cycle:
    """A completed cycle: from one period start up to the day before the next."""

    start: date
    end: date
    length: int


# --- connection ---------------------------------------------------------------

def init_schema(conn: sqlite3.Connection) -> None:
    """Create every table (users first, since the others reference it)."""
    auth.init_schema(conn)
    conn.executescript(SCHEMA)
    migrate(conn)


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Bring an older database up to the current schema, additively.

    Only adds what's missing (new tables come from SCHEMA's CREATE TABLE
    IF NOT EXISTS; new columns are added here). Never rewrites, copies or
    deletes a row. Safe to run on every connect. Returns what it added.
    """
    added = []
    with conn:
        for table, column, decl in NEW_COLUMNS:
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
                added.append(f"{table}.{column}")
    return added


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database file (creating it if needed) with foreign keys on.

    secure_delete makes SQLite overwrite deleted rows with zeros instead
    of leaving them in free pages of the file, so "delete all my data"
    really removes it from disk (spec.md Feature 7).
    """
    path = Path(path) if path is not None else db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA secure_delete = ON")
    init_schema(conn)
    return conn


def delete_account(conn: sqlite3.Connection, user_id: int, confirm_email: str) -> None:
    """Delete everything for a user: logs, cycles, partner links (both
    directions), and the account itself.

    `confirm_email` must match the account's email (case-insensitive) —
    the UI's typed confirmation, checked here so no caller can skip it.
    """
    user = auth.get_user(conn, user_id)
    if user is None:
        raise ValueError("No such account.")
    if auth.normalize_email(confirm_email) != user.email:
        raise ValueError("That email doesn't match this account — nothing was deleted.")
    with conn:
        conn.execute("DELETE FROM daily_symptom WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM daily_strategy WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM daily_log WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM cycle WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM remedy_log WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM user_settings WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM phase_guide WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM llm_usage WHERE user_id = ?", (user_id,))
        conn.execute(
            "DELETE FROM partner_links WHERE user_id = ? OR partner_user_id = ?",
            (user_id, user_id),
        )
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))


# --- daily logs ---------------------------------------------------------------

def _write_log(conn: sqlite3.Connection, user_id: int, entry: LogEntry) -> None:
    """Write one day's rows. Call inside a transaction, then rebuild cycles."""
    day = entry.date.isoformat()
    conn.execute(
        "INSERT OR REPLACE INTO daily_log"
        " (user_id, date, flow, mood, poor_sleep, high_stress, travel, day_rating, energy)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            user_id, day, entry.flow, entry.mood,
            int(entry.poor_sleep), int(entry.high_stress), int(entry.travel),
            entry.day_rating, entry.energy,
        ),
    )
    # INSERT OR REPLACE deletes the old row, which cascades to its
    # symptoms only when foreign keys are on — clear them explicitly
    # so replacement never depends on the connection's pragmas.
    for table in ("daily_symptom", "daily_strategy"):
        conn.execute(f"DELETE FROM {table} WHERE user_id = ? AND date = ?", (user_id, day))
    conn.executemany(
        "INSERT INTO daily_symptom (user_id, date, symptom) VALUES (?, ?, ?)",
        [(user_id, day, s) for s in sorted(entry.symptoms)],
    )
    conn.executemany(
        "INSERT INTO daily_strategy (user_id, date, strategy) VALUES (?, ?, ?)",
        [(user_id, day, s) for s in sorted(entry.strategies)],
    )


def save_log(conn: sqlite3.Connection, user_id: int, entry: LogEntry) -> None:
    """Save one day's log for a user, replacing anything already logged that day."""
    with conn:
        _write_log(conn, user_id, entry)
        _rebuild_cycles(conn, user_id)


def save_logs(conn: sqlite3.Connection, user_id: int, entries: list[LogEntry]) -> None:
    """save_log for many days in one transaction (one cycle rebuild).
    Used to seed the demo account."""
    with conn:
        for entry in entries:
            _write_log(conn, user_id, entry)
        _rebuild_cycles(conn, user_id)


def delete_log(conn: sqlite3.Connection, user_id: int, day: date) -> None:
    """Remove one day's log (and its symptoms and strategies) for a user."""
    with conn:
        for table in ("daily_symptom", "daily_strategy"):
            conn.execute(f"DELETE FROM {table} WHERE user_id = ? AND date = ?", (user_id, day.isoformat()))
        conn.execute(
            "DELETE FROM daily_log WHERE user_id = ? AND date = ?", (user_id, day.isoformat())
        )
        _rebuild_cycles(conn, user_id)


def get_logs(
    conn: sqlite3.Connection, user_id: int, start: date | None = None, end: date | None = None
) -> list[LogEntry]:
    """A user's logs in date order, optionally limited to start..end inclusive."""
    query = (
        "SELECT date, flow, mood, poor_sleep, high_stress, travel, day_rating, energy"
        " FROM daily_log WHERE user_id = ?"
    )
    params: list = [user_id]
    if start is not None:
        query += " AND date >= ?"
        params.append(start.isoformat())
    if end is not None:
        query += " AND date <= ?"
        params.append(end.isoformat())
    rows = conn.execute(query + " ORDER BY date", params).fetchall()

    symptoms: dict[str, set[str]] = {}
    for day, symptom in conn.execute(
        "SELECT date, symptom FROM daily_symptom WHERE user_id = ?", (user_id,)
    ):
        symptoms.setdefault(day, set()).add(symptom)
    strategies: dict[str, set[str]] = {}
    for day, strategy in conn.execute(
        "SELECT date, strategy FROM daily_strategy WHERE user_id = ?", (user_id,)
    ):
        strategies.setdefault(day, set()).add(strategy)

    return [
        LogEntry(
            date=date.fromisoformat(day),
            flow=flow,
            mood=mood,
            symptoms=frozenset(symptoms.get(day, ())),
            poor_sleep=bool(poor_sleep),
            high_stress=bool(high_stress),
            travel=bool(travel),
            day_rating=day_rating,
            energy=energy,
            strategies=frozenset(strategies.get(day, ())),
        )
        for day, flow, mood, poor_sleep, high_stress, travel, day_rating, energy in rows
    ]


def get_log(conn: sqlite3.Connection, user_id: int, day: date) -> LogEntry | None:
    logs = get_logs(conn, user_id, day, day)
    return logs[0] if logs else None


# --- cycles -------------------------------------------------------------------

def period_starts(bleeding_days: list[date]) -> list[date]:
    """Period start dates from a user's bleeding days (any order, duplicates ok).

    A bleeding day is a start if it's the first one ever, or if the
    PERIOD_GAP_DAYS days before it were all non-bleeding.
    """
    days = sorted(set(bleeding_days))
    return [
        d for i, d in enumerate(days)
        if i == 0 or (d - days[i - 1]).days > PERIOD_GAP_DAYS
    ]


def cycles_from_starts(starts: list[date]) -> list[Cycle]:
    """Completed cycles between consecutive starts; the open cycle is excluded."""
    return [
        Cycle(start=a, end=b - timedelta(days=1), length=(b - a).days)
        for a, b in zip(starts, starts[1:])
    ]


def _bleeding_days(conn: sqlite3.Connection, user_id: int) -> list[date]:
    return [
        date.fromisoformat(row[0])
        for row in conn.execute(
            f"SELECT date FROM daily_log WHERE user_id = ? AND flow IN ({_sql_list(BLEEDING_FLOWS)})",
            (user_id,),
        )
    ]


def _rebuild_cycles(conn: sqlite3.Connection, user_id: int) -> None:
    """Recompute a user's cycle rows from their logs. Call inside a transaction."""
    bleeding = _bleeding_days(conn, user_id)
    conn.execute("DELETE FROM cycle WHERE user_id = ?", (user_id,))
    conn.executemany(
        "INSERT INTO cycle (user_id, start_date, end_date, length) VALUES (?, ?, ?, ?)",
        [
            (user_id, c.start.isoformat(), c.end.isoformat(), c.length)
            for c in cycles_from_starts(period_starts(bleeding))
        ],
    )


def get_cycles(conn: sqlite3.Connection, user_id: int) -> list[Cycle]:
    """A user's completed cycles, oldest first."""
    return [
        Cycle(date.fromisoformat(start), date.fromisoformat(end), length)
        for start, end, length in conn.execute(
            "SELECT start_date, end_date, length FROM cycle WHERE user_id = ? ORDER BY start_date",
            (user_id,),
        )
    ]


def get_period_starts(conn: sqlite3.Connection, user_id: int) -> list[date]:
    """Every period start for a user, including the current (open) cycle's."""
    return period_starts(_bleeding_days(conn, user_id))


# --- remedies -----------------------------------------------------------------

@dataclass(frozen=True)
class RemedyEntry:
    date: date
    symptom: str
    remedy: str  # normalized: lowercase, underscores for spaces
    relief_rating: int


def add_remedy(
    conn: sqlite3.Connection, user_id: int, day: date, symptom: str, remedy: str, relief_rating: int
) -> RemedyEntry:
    """Log what was tried for a symptom and how much it helped (1–5)."""
    if symptom not in SYMPTOMS:
        raise ValueError(f"unknown symptom {symptom!r}; allowed: {SYMPTOMS}")
    if not 1 <= relief_rating <= 5:
        raise ValueError(f"relief_rating must be 1–5, got {relief_rating}")
    entry = RemedyEntry(day, symptom, normalize_remedy(remedy), relief_rating)
    with conn:
        conn.execute(
            "INSERT INTO remedy_log (user_id, date, symptom, remedy, relief_rating)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, day.isoformat(), entry.symptom, entry.remedy, entry.relief_rating),
        )
    return entry


def get_remedies(conn: sqlite3.Connection, user_id: int) -> list[RemedyEntry]:
    """A user's remedy log, oldest first."""
    return [
        RemedyEntry(date.fromisoformat(d), symptom, remedy, rating)
        for d, symptom, remedy, rating in conn.execute(
            "SELECT date, symptom, remedy, relief_rating FROM remedy_log"
            " WHERE user_id = ? ORDER BY date, id",
            (user_id,),
        )
    ]


def past_remedies(conn: sqlite3.Connection, user_id: int, symptom: str | None = None) -> list[str]:
    """Remedies this user has logged before (for "pick from past entries"),
    most used first."""
    query = "SELECT remedy FROM remedy_log WHERE user_id = ?"
    params: list = [user_id]
    if symptom is not None:
        query += " AND symptom = ?"
        params.append(symptom)
    query += " GROUP BY remedy ORDER BY COUNT(*) DESC, remedy"
    return [row[0] for row in conn.execute(query, params)]


# --- Level 2 settings -----------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """A user's Level 2 settings. None means "not set" (spec.md Data)."""

    luteal_days: int | None = None  # None = predict.LUTEAL_DAYS (14)
    hormonal_contraception: bool = False
    phase_guide_opt_in: bool = False
    week_fit_opt_in: bool = False
    is_demo: bool = False


_SETTING_COLUMNS = tuple(Settings.__dataclass_fields__)


def get_settings(conn: sqlite3.Connection, user_id: int) -> Settings:
    row = conn.execute(
        f"SELECT {', '.join(_SETTING_COLUMNS)} FROM user_settings WHERE user_id = ?", (user_id,)
    ).fetchone()
    if row is None:
        return Settings()
    luteal, *flags = row
    return Settings(luteal, *(bool(f) for f in flags))


def update_settings(conn: sqlite3.Connection, user_id: int, **changes) -> Settings:
    """Change some settings, leaving the rest as they are."""
    unknown = set(changes) - set(_SETTING_COLUMNS)
    if unknown:
        raise ValueError(f"unknown settings {sorted(unknown)}")
    luteal = changes.get("luteal_days")
    if luteal is not None and not LUTEAL_DAYS_RANGE[0] <= luteal <= LUTEAL_DAYS_RANGE[1]:
        raise ValueError(f"luteal_days must be {LUTEAL_DAYS_RANGE[0]}–{LUTEAL_DAYS_RANGE[1]}, got {luteal}")
    values = {k: (int(v) if isinstance(v, bool) else v) for k, v in changes.items()}
    with conn:
        conn.execute("INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)", (user_id,))
        for column, value in values.items():
            conn.execute(f"UPDATE user_settings SET {column} = ? WHERE user_id = ?", (value, user_id))
    return get_settings(conn, user_id)
