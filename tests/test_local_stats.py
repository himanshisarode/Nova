"""Phase 7.5, beyond the fixed contract tests (test_lifestyle_link.py and
test_remedy.py, which stay as hand-written): tag grouping from real logs,
remedy normalization and storage, sentences, and no network access."""
import ast
import io
import socket
import sqlite3
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

import auth
import db
import export
import lifestyle_link
import remedy

ROOT = Path(__file__).parent.parent


@pytest.fixture
def conn(tmp_path):
    conn = db.connect(tmp_path / "nova.db")
    yield conn
    conn.close()


@pytest.fixture
def user(conn):
    return auth.signup(conn, "a@example.com", "password-a-123", "A").id


# --- lifestyle link: grouping cycles by tag -----------------------------------

def _cycle(start, length):
    return db.Cycle(start, start + timedelta(days=length - 1), length)


def test_tag_on_any_single_day_marks_the_cycle():
    start = date(2026, 1, 1)
    logs = [db.LogEntry(start + timedelta(days=20), high_stress=True),
            db.LogEntry(start + timedelta(days=30), travel=True)]  # next cycle
    rows = lifestyle_link.cycles_with_tags([_cycle(start, 28), _cycle(start + timedelta(days=28), 28)], logs)
    assert rows == [{"length": 28, "tags": ["high_stress"]}, {"length": 28, "tags": ["travel"]}]


def test_end_to_end_from_logged_days(conn, user):
    # Cycles 31, 33, 30, 32 with high stress logged on one day each, then
    # 28, 27, 29, 28 without — the fixed test's numbers, but going through
    # db and the tag grouping instead of hand-built dicts.
    start = date(2026, 1, 1)
    for i, length in enumerate([31, 33, 30, 32, 28, 27, 29, 28]):
        db.save_log(conn, user, db.LogEntry(start, flow="medium"))
        if i < 4:
            db.save_log(conn, user, db.LogEntry(start + timedelta(days=10), high_stress=True))
        start += timedelta(days=length)
    db.save_log(conn, user, db.LogEntry(start, flow="medium"))  # closes the last cycle

    rows = lifestyle_link.cycles_with_tags(db.get_cycles(conn, user), db.get_logs(conn, user))
    results = lifestyle_link.all_links(rows)
    assert results["high_stress"]["significant"] is True
    assert results["poor_sleep"]["status"] == "not_enough_data"  # 0 tagged cycles
    assert lifestyle_link.describe(results["high_stress"], "high_stress") == (
        "Cycles with high stress logged ran 3.5 days longer on average (31.5 vs 28.0 days)."
    )


def test_identical_groups_with_no_spread_are_not_a_link():
    rows = [{"length": 28, "tags": ["travel"]}] * 3 + [{"length": 28, "tags": []}] * 3
    result = lifestyle_link.check_lifestyle_link(rows, "travel")
    assert result["status"] == "result" and result["significant"] is False


def test_sentences_for_no_link_and_not_enough_data():
    assert lifestyle_link.describe({"status": "result", "significant": False}, "poor_sleep") == (
        "No significant link found yet between poor sleep and your cycle length."
    )
    text = lifestyle_link.describe({"status": "not_enough_data"}, "travel")
    assert "at least 3" in text and "travel" in text


def test_not_enough_data_reports_counts_for_progress():
    rows = [{"length": 30, "tags": ["travel"]}] * 2 + [{"length": 28, "tags": []}] * 5
    assert lifestyle_link.check_lifestyle_link(rows, "travel") == {
        "status": "not_enough_data", "n_with": 2, "n_without": 5,
    }


# --- remedy: normalization and ranking ----------------------------------------

@pytest.mark.parametrize("typed", ["Heat Pad", " heat pad ", "heat_pad", "HEAT   PAD", "Heat\tPad"])
def test_remedy_spellings_normalize_together(typed):
    assert remedy.normalize_remedy(typed) == "heat_pad"


@pytest.mark.parametrize("typed", ["", "   "])
def test_empty_remedy_rejected(typed):
    with pytest.raises(ValueError):
        remedy.normalize_remedy(typed)


def test_differently_typed_spellings_pool_into_one_ranked_pair():
    logs = [
        {"symptom": "cramps", "remedy": "Heat Pad", "relief_rating": 4},
        {"symptom": "cramps", "remedy": "heat_pad", "relief_rating": 5},
        {"symptom": "cramps", "remedy": " heat pad", "relief_rating": 3},
    ]
    [entry] = remedy.remedy_effectiveness(logs)["cramps"]
    assert entry == {"remedy": "heat_pad", "avg_rating": 4.0, "n": 3, "status": "ranked"}


def test_not_enough_data_entries_have_no_average_and_sort_last():
    logs = (
        [{"symptom": "cramps", "remedy": "walking", "relief_rating": 5}] * 2
        + [{"symptom": "cramps", "remedy": "ibuprofen", "relief_rating": 2}] * 3
    )
    entries = remedy.remedy_effectiveness(logs)["cramps"]
    assert [(e["remedy"], e["status"]) for e in entries] == [
        ("ibuprofen", "ranked"), ("walking", "not_enough_data"),
    ]
    assert entries[1]["avg_rating"] is None


def test_remedy_sentences():
    assert remedy.describe({"remedy": "heat_pad", "avg_rating": 4.25, "n": 4, "status": "ranked"}) == (
        "heat pad: 4.2 / 5 average relief (4 times)"
    )
    assert remedy.describe({"remedy": "walking", "avg_rating": None, "n": 1, "status": "not_enough_data"}) == (
        "walking: logged 1 time so far — 2 more and Nova can show how well it tends to help."
    )


# --- remedy: storage ----------------------------------------------------------

def test_remedies_stored_normalized_and_per_user(conn, user):
    other = auth.signup(conn, "b@example.com", "password-b-123", "B").id
    db.add_remedy(conn, user, date(2026, 1, 2), "cramps", "  Heat Pad ", 4)
    db.add_remedy(conn, user, date(2026, 1, 3), "cramps", "heat_pad", 5)
    db.add_remedy(conn, user, date(2026, 1, 3), "headache", "Water", 3)
    db.add_remedy(conn, other, date(2026, 1, 3), "cramps", "yoga", 2)

    assert [r.remedy for r in db.get_remedies(conn, user)] == ["heat_pad", "heat_pad", "water"]
    assert db.past_remedies(conn, user) == ["heat_pad", "water"]
    assert db.past_remedies(conn, user, "headache") == ["water"]
    assert db.past_remedies(conn, other) == ["yoga"]


@pytest.mark.parametrize("symptom, rating", [("sneezing", 3), ("cramps", 0), ("cramps", 6)])
def test_invalid_remedy_entries_rejected(conn, user, symptom, rating):
    with pytest.raises(ValueError):
        db.add_remedy(conn, user, date(2026, 1, 2), symptom, "tea", rating)


def test_database_rejects_unnormalized_remedy_text(conn, user):
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO remedy_log (user_id, date, symptom, remedy, relief_rating)"
            " VALUES (?, '2026-01-02', 'cramps', 'Heat Pad', 3)", (user,),
        )


def test_remedy_log_in_export_and_gone_after_delete(tmp_path):
    path = tmp_path / "nova.db"
    conn = db.connect(path)
    uid = auth.signup(conn, "a@example.com", "password-a-123", "A").id
    db.add_remedy(conn, uid, date(2026, 1, 2), "cramps", "Zephyr Moon Tea", 4)

    with zipfile.ZipFile(io.BytesIO(export.export_my_data(conn, uid))) as zf:
        assert zf.read("remedy_log.csv").decode().splitlines() == [
            "date,symptom,remedy,relief_rating", "2026-01-02,cramps,zephyr_moon_tea,4",
        ]

    db.delete_account(conn, uid, "a@example.com")
    conn.close()
    assert b"zephyr_moon_tea" not in path.read_bytes()


# --- no network ---------------------------------------------------------------

def test_no_network_fixture_really_blocks(no_network):
    # Control: the fixture must actually stop a connection attempt.
    with pytest.raises(AssertionError, match="network access attempted"):
        socket.create_connection(("example.com", 80), timeout=1)


def test_lifestyle_link_makes_no_network_calls(conn, user, no_network):
    rows = [{"length": n, "tags": ["high_stress"]} for n in (31, 33, 30, 32)]
    rows += [{"length": n, "tags": []} for n in (28, 27, 29, 28)]
    lifestyle_link.describe(lifestyle_link.check_lifestyle_link(rows, "high_stress"), "high_stress")
    lifestyle_link.all_links(rows)
    lifestyle_link.cycles_with_tags(db.get_cycles(conn, user), db.get_logs(conn, user))


def test_remedy_makes_no_network_calls(conn, user, no_network):
    db.add_remedy(conn, user, date(2026, 1, 2), "cramps", "heat pad", 4)
    logs = [{"symptom": r.symptom, "remedy": r.remedy, "relief_rating": r.relief_rating}
            for r in db.get_remedies(conn, user)]
    for entry in remedy.remedy_effectiveness(logs)["cramps"]:
        remedy.describe(entry)


@pytest.mark.parametrize("module", ["lifestyle_link.py", "remedy.py"])
def test_modules_import_nothing_network_capable(module):
    tree = ast.parse((ROOT / module).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    banned = {"socket", "urllib", "http", "requests", "httpx", "aiohttp", "anthropic", "openai"}
    assert not imported & banned
