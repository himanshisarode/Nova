"""Demo mode (spec.md Feature 21).

One clearly labelled demo account, seeded from simulate.py with 10
completed cycles (over 8 months) of logs, day ratings and strategies, and
a planted per-phase effect, so the personalised features can be shown
live past the 6-month gate. The same seeding is the end-to-end test
fixture (tests/test_demo.py).

It can't mix with real accounts: it can't save logs or remedies
(db.DemoReadOnly), can't create or redeem invites (partner.py), and
signup refuses its reserved @nova.invalid domain (auth.py). It has no
usable password: it is entered only through "Try the demo".
"""
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone

import bcrypt

import auth
import db
import simulate

DEMO_EMAIL = "demo" + auth.RESERVED_EMAIL_DOMAIN
DEMO_NAME = "Demo (sample data)"
BANNER = "Demo data — not a real person. Nothing you see here is anyone's health information."
DEMO_SEED = 4  # chosen so all three planted effects clear the bar (tests/test_demo.py)
DEMO_CYCLES = 10
OPEN_CYCLE_DAY = 9  # "today" is day 9 of the demo's current cycle
PLANTED = {
    ("follicular", "strength"): 1.2,
    ("luteal", "early_night"): 1.2,
    ("period", "walk"): 1.2,
}


def demo_logs(today: date) -> list[db.LogEntry]:
    """The demo's synthetic logs, shifted so the open cycle started
    OPEN_CYCLE_DAY − 1 days before `today` and nothing is after today."""
    # Simulate one cycle more than needed and cut it off at today, so the
    # open cycle is logged every day up to today (the simulator otherwise
    # stops after the last period).
    h = simulate.simulate_history(DEMO_SEED, n_cycles=DEMO_CYCLES + 1, irregular_rate=0.0)
    shift = (today - timedelta(days=OPEN_CYCLE_DAY - 1)) - h.starts[-2]
    out = []
    for e in simulate.with_strategies(h, DEMO_SEED, PLANTED):
        day = e.date + shift
        if day <= today:
            out.append(db.LogEntry(day, e.flow, e.mood, e.symptoms, e.poor_sleep, e.high_stress,
                                   e.travel, e.day_rating, e.energy, e.strategies))
    return out


def demo_user_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT id FROM users WHERE email = ?", (DEMO_EMAIL,)).fetchone()
    return row[0] if row and db.get_settings(conn, row[0]).is_demo else None


def ensure_demo(conn: sqlite3.Connection, today: date | None = None) -> auth.User:
    """Create the demo account if needed and make sure its data runs up to
    today (re-seeding synthetic rows only). Returns the demo user."""
    today = today or date.today()
    user_id = demo_user_id(conn)
    if user_id is None:
        # No usable password: a random secret nobody knows, hashed like any other.
        unusable = bcrypt.hashpw(secrets.token_bytes(32).hex().encode(), bcrypt.gensalt()).decode()
        with conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, display_name, created_at) VALUES (?, ?, ?, ?)",
                (DEMO_EMAIL, unusable, DEMO_NAME, datetime.now(timezone.utc).isoformat(timespec="seconds")),
            )
        user_id = cur.lastrowid
        db.update_settings(conn, user_id, is_demo=True)
    last = conn.execute("SELECT MAX(date) FROM daily_log WHERE user_id = ?", (user_id,)).fetchone()[0]
    if last != today.isoformat():
        db.replace_demo_logs(conn, user_id, demo_logs(today))
    return auth.get_user(conn, user_id)


def is_demo(conn: sqlite3.Connection, user_id: int) -> bool:
    return db.get_settings(conn, user_id).is_demo
