"""Phase 12: llm.py — the one door to the provider (spec.md LLM layer).

The provider is faked at the HTTP layer (tests/conftest.py fake_llm), and
the no_network guard is on for every test that uses it.
"""
import ast
import logging
import re
import subprocess
from pathlib import Path

import pytest

import auth
import db
import llm

ROOT = Path(__file__).parent.parent
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}},
          "required": ["ok"], "additionalProperties": False}


@pytest.fixture
def conn(tmp_path):
    conn = db.connect(tmp_path / "nova.db")
    yield conn
    conn.close()


@pytest.fixture
def users(conn):
    return [auth.signup(conn, f"u{i}@example.com", "password-123456", f"U{i}").id for i in (1, 2)]


def call(conn, user, call_type="phase_guide", payload=None):
    return llm.request(conn, user, call_type, "system text", payload or {"x": 1}, SCHEMA)


def test_a_reply_comes_back_as_parsed_json(conn, users, fake_llm):
    fake_llm.reply = {"ok": True}
    assert call(conn, users[0]) == {"ok": True}
    body = fake_llm.requests[0]
    assert body["model"] == llm.MODEL
    assert body["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}}
    assert body["fallbacks"] == "default"
    assert body["system"] == "system text"
    assert [m["role"] for m in body["messages"]] == ["user"]  # one request, one reply
    assert "tools" not in body


def test_only_two_call_types_exist(conn, users, fake_llm):
    assert llm.CALL_TYPES == ("phase_guide", "week_fit")
    with pytest.raises(ValueError):
        call(conn, users[0], "explain_my_trend")
    assert fake_llm.requests == []


def test_only_the_two_feature_modules_import_llm():
    importers = set()
    for path in ROOT.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module] if isinstance(node, ast.ImportFrom) else [])
            if "llm" in names:
                importers.add(path.name)
    # week_fit.py arrives in Phase 14; nothing else may ever import llm.
    assert "phase_guide.py" in importers and importers <= {"phase_guide.py", "week_fit.py"}


def test_no_key_means_no_request_and_no_slot_used(conn, users, fake_llm, monkeypatch):
    monkeypatch.delenv(llm.API_KEY_ENV)
    with pytest.raises(llm.LLMUnavailable):
        call(conn, users[0])
    assert fake_llm.requests == [] and llm.usage_today(conn, users[0], "phase_guide") == 0


def test_daily_cap_blocks_call_n_plus_1_per_user_and_per_type(conn, users, fake_llm):
    fake_llm.reply = {"ok": True}
    a, b = users
    for _ in range(llm.DAILY_CAPS["phase_guide"]):
        call(conn, a)
    with pytest.raises(llm.CapReached):
        call(conn, a)
    assert len(fake_llm.requests) == 3  # the blocked call never left the machine
    call(conn, b)  # another user has their own cap
    for _ in range(llm.DAILY_CAPS["week_fit"]):
        call(conn, a, "week_fit")  # another call type has its own cap
    with pytest.raises(llm.CapReached):
        call(conn, a, "week_fit")
    assert llm.DAILY_CAPS == {"phase_guide": 3, "week_fit": 5}


def test_failed_calls_count_toward_the_cap(conn, users, fake_llm):
    fake_llm.status = 500
    for _ in range(3):
        with pytest.raises(llm.LLMUnavailable):
            call(conn, users[0])
    fake_llm.status = 200
    fake_llm.reply = {"ok": True}
    with pytest.raises(llm.CapReached):
        call(conn, users[0])


@pytest.mark.parametrize("setup", [
    {"status": 500}, {"status": 401}, {"status": 429},
    {"raw_text": "not json"}, {"raw_text": "[1, 2]"}, {"stop_reason": "max_tokens"},
    {"stop_reason": "refusal"},
])
def test_provider_problems_become_llm_unavailable(conn, users, fake_llm, setup):
    fake_llm.reply = {"ok": True}
    for k, v in setup.items():
        setattr(fake_llm, k, v)
    with pytest.raises(llm.LLMUnavailable):
        call(conn, users[0])


def test_nothing_from_the_payload_or_reply_is_logged(conn, users, fake_llm, caplog):
    caplog.set_level(logging.DEBUG)
    fake_llm.reply = {"ok": True, "secret_reply": "zebra-reply-text"}
    call(conn, users[0], payload={"note": "zebra-payload-text"})
    fake_llm.status = 500
    with pytest.raises(llm.LLMUnavailable):
        call(conn, users[0], payload={"note": "zebra-payload-text"})
    assert "zebra" not in caplog.text


def test_no_api_key_in_tracked_files():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                           check=True).stdout.split()
    pattern = re.compile(r"sk-ant-[A-Za-z0-9_-]{10,}")
    for name in files:
        path = ROOT / name
        if path.suffix in {".png", ".woff2", ".ttf", ".pdf", ".db"} or not path.is_file():
            continue
        assert not pattern.search(path.read_text(encoding="utf-8", errors="ignore")), name
    assert ".env" in (ROOT / ".gitignore").read_text().split()
