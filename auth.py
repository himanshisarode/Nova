"""Accounts for Nova: the users table, signup, login, and the tab session.

Passwords are only ever stored as bcrypt hashes (SPEC.md Architecture —
non-negotiable). Functions take an open sqlite3 connection so the caller
decides which database file is used; nothing here holds a connection.

Session handling is deliberately minimal (SPEC.md): the logged-in user
lives in Streamlit session state for the life of the browser tab. No
cookies, no remember-me tokens.
"""
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

import bcrypt
import streamlit as st

MIN_PASSWORD_LENGTH = 8
# bcrypt only looks at the first 72 bytes; longer passwords are rejected
# rather than silently truncated.
MAX_PASSWORD_BYTES = 72
SESSION_KEY = "nova_user"
# The demo account lives here (.invalid can never be a real address), so a
# real signup can never collide with or impersonate it (spec.md Feature 21).
RESERVED_EMAIL_DOMAIN = "@nova.invalid"

# Deliberately loose: "something@something.something". Real verification
# would need email delivery, which this project doesn't have.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    display_name  TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""

# Checked against when the email doesn't exist, so a login attempt takes
# about the same time whether or not the account is real.
_DUMMY_HASH = bcrypt.hashpw(b"nova-dummy-password", bcrypt.gensalt())


class SignupError(ValueError):
    """Signup was refused; the message is safe to show to the user."""


@dataclass(frozen=True)
class User:
    id: int
    email: str
    display_name: str
    created_at: str


def init_schema(conn: sqlite3.Connection) -> None:
    """Create the users table if it doesn't exist yet."""
    conn.executescript(USERS_SCHEMA)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def signup(conn: sqlite3.Connection, email: str, password: str, display_name: str) -> User:
    """Create an account and return it. Raises SignupError if refused."""
    email = normalize_email(email)
    display_name = display_name.strip()
    if not _EMAIL_RE.match(email):
        raise SignupError("That doesn't look like an email address.")
    if email.endswith(RESERVED_EMAIL_DOMAIN):
        raise SignupError("That email address is reserved for Nova's demo.")
    if not display_name:
        raise SignupError("Please tell us what to call you.")
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SignupError(f"Passwords need at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise SignupError(f"Passwords can be at most {MAX_PASSWORD_BYTES} bytes long.")

    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO users (email, password_hash, display_name, created_at)"
                " VALUES (?, ?, ?, ?)",
                (email, password_hash, display_name, created_at),
            )
    except sqlite3.IntegrityError:
        raise SignupError("An account with that email already exists.") from None
    return User(cur.lastrowid, email, display_name, created_at)


def login(conn: sqlite3.Connection, email: str, password: str) -> User | None:
    """Return the user if the email and password match, otherwise None.

    Unknown email and wrong password look identical to the caller, so the
    login form can't be used to discover who has an account.
    """
    row = conn.execute(
        "SELECT id, email, password_hash, display_name, created_at FROM users WHERE email = ?",
        (normalize_email(email),),
    ).fetchone()
    candidate = password.encode("utf-8")
    if row is None or len(candidate) > MAX_PASSWORD_BYTES:
        bcrypt.checkpw(b"nova-dummy-password", _DUMMY_HASH)
        return None
    user_id, stored_email, password_hash, display_name, created_at = row
    if not bcrypt.checkpw(candidate, password_hash.encode("ascii")):
        return None
    return User(user_id, stored_email, display_name, created_at)


def get_user(conn: sqlite3.Connection, user_id: int) -> User | None:
    row = conn.execute(
        "SELECT id, email, display_name, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    return User(*row) if row else None


# --- Tab session ---------------------------------------------------------------

def start_session(user: User) -> None:
    """Mark `user` as logged in for this browser tab."""
    st.session_state[SESSION_KEY] = user


def current_user() -> User | None:
    """The user logged in on this tab, or None."""
    return st.session_state.get(SESSION_KEY)


def end_session() -> None:
    """Log out of this tab."""
    st.session_state.pop(SESSION_KEY, None)
