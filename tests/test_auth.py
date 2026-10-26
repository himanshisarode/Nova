"""Phase 1: signup, login, password storage, and the tab session."""
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

import auth

PASSWORD = "lavender-moon-42"


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "nova.db"
    conn = sqlite3.connect(path)
    auth.init_schema(conn)
    conn.close()
    return path


@pytest.fixture
def conn(db_path):
    conn = sqlite3.connect(db_path)
    yield conn
    conn.close()


# --- signup -------------------------------------------------------------------

def test_signup_returns_user_with_normalized_email(conn):
    user = auth.signup(conn, "  Maya@Example.COM ", PASSWORD, " Maya ")
    assert user.id is not None
    assert user.email == "maya@example.com"
    assert user.display_name == "Maya"


def test_duplicate_email_rejected_case_insensitively(conn):
    auth.signup(conn, "maya@example.com", PASSWORD, "Maya")
    with pytest.raises(auth.SignupError, match="already exists"):
        auth.signup(conn, "MAYA@example.com", "another-password", "Someone")


@pytest.mark.parametrize(
    "email, password, name, message",
    [
        ("not-an-email", PASSWORD, "Maya", "email"),
        ("maya@example.com", "short", "Maya", "at least"),
        ("maya@example.com", "x" * 73, "Maya", "at most"),
        ("maya@example.com", PASSWORD, "   ", "call you"),
    ],
)
def test_invalid_signup_rejected(conn, email, password, name, message):
    with pytest.raises(auth.SignupError, match=message):
        auth.signup(conn, email, password, name)
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0


# --- login --------------------------------------------------------------------

def test_login_with_correct_password(conn):
    created = auth.signup(conn, "maya@example.com", PASSWORD, "Maya")
    assert auth.login(conn, "Maya@Example.com", PASSWORD) == created


def test_login_with_wrong_password_fails(conn):
    auth.signup(conn, "maya@example.com", PASSWORD, "Maya")
    assert auth.login(conn, "maya@example.com", "lavender-moon-43") is None


def test_login_with_unknown_email_fails(conn):
    assert auth.login(conn, "nobody@example.com", PASSWORD) is None


def test_login_with_overlong_password_fails_cleanly(conn):
    auth.signup(conn, "maya@example.com", PASSWORD, "Maya")
    assert auth.login(conn, "maya@example.com", "x" * 100) is None


def test_user_can_log_back_in_after_restart(db_path):
    first = sqlite3.connect(db_path)
    created = auth.signup(first, "maya@example.com", PASSWORD, "Maya")
    first.close()

    # A fresh connection to the same file stands in for an app restart.
    second = sqlite3.connect(db_path)
    try:
        assert auth.login(second, "maya@example.com", PASSWORD) == created
        assert auth.get_user(second, created.id) == created
    finally:
        second.close()


# --- password storage ---------------------------------------------------------

def test_no_plaintext_password_in_database_file(db_path):
    conn = sqlite3.connect(db_path)
    auth.signup(conn, "maya@example.com", PASSWORD, "Maya")
    stored = conn.execute("SELECT password_hash FROM users").fetchone()[0]
    conn.close()

    raw = db_path.read_bytes()
    assert b"maya@example.com" in raw  # sanity check: we're reading the right file
    assert PASSWORD.encode() not in raw
    assert stored.startswith("$2b$")  # bcrypt


def test_same_password_hashes_differently_per_user(conn):
    auth.signup(conn, "a@example.com", PASSWORD, "A")
    auth.signup(conn, "b@example.com", PASSWORD, "B")
    hashes = [row[0] for row in conn.execute("SELECT password_hash FROM users")]
    assert hashes[0] != hashes[1]


# --- tab session --------------------------------------------------------------

def test_session_start_and_end():
    def page():
        import streamlit as st

        import auth

        st.write(f"before: {auth.current_user()}")
        auth.start_session(auth.User(1, "maya@example.com", "Maya", "2026-10-27T00:00:00+00:00"))
        st.write(f"during: {auth.current_user().display_name}")
        auth.end_session()
        st.write(f"after: {auth.current_user()}")

    at = AppTest.from_function(page).run()
    assert not at.exception
    assert [m.value for m in at.markdown] == ["before: None", "during: Maya", "after: None"]
