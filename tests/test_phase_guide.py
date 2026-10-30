"""Phase 12: Phase Guide (spec.md Feature 22, LLM layer call 1)."""
import json
import re
from datetime import date

import pytest

import auth
import db
import llm
import phase_guide
import wording

FINDINGS = {
    "period": [("walk", "moderate evidence")],
    "follicular": [("strength", "strong evidence"), ("social_plans", "early sign")],
    "luteal": [],
}
RANGE = (27, 31)
CYCLE = date(2026, 9, 3)

GOOD_REPLY = {
    "phases": [
        {"phase": "Period days", "text": "In your data, days with a walk tend to go well on period days (moderate evidence)."},
        {"phase": "Follicular phase", "text": "Strength training tends to go well for you here, and social plans show an early sign too."},
        {"phase": "Luteal phase", "text": "Nothing stands out clearly in your data for this phase yet."},
    ],
    "cycle_sentence": "Your cycles have usually run between 27 and 31 days.",
}


@pytest.fixture
def conn(tmp_path):
    conn = db.connect(tmp_path / "nova.db")
    yield conn
    conn.close()


@pytest.fixture
def user(conn):
    u = auth.signup(conn, "maya.private@example.com", "password-123456", "Maya Q").id
    db.save_log(conn, u, db.LogEntry(date(2026, 9, 3), flow="heavy", mood=2, symptoms={"cramps"},
                                     day_rating=4, strategies={"walk"}))
    db.update_settings(conn, u, phase_guide_opt_in=True)
    return u


def generate(conn, user, **kw):
    return phase_guide.generate(conn, user, FINDINGS, RANGE, CYCLE, gate_open=kw.pop("gate_open", True), **kw)


# --- what leaves the machine ---------------------------------------------------------

def test_real_request_body_holds_only_labels_tiers_and_two_numbers(conn, user, fake_llm):
    fake_llm.reply = GOOD_REPLY
    generate(conn, user)
    sent = fake_llm.user_payload()
    assert sent == phase_guide.payload(FINDINGS, RANGE)
    text = json.dumps(fake_llm.requests[0])
    # (the user id is covered by the digits check below)
    for private in ("maya", "Maya Q", "example.com", "2026", "09-03", "cramps"):
        assert private.lower() not in text.lower(), private
    # The only numbers in the user content are the two cycle lengths.
    assert {int(n) for n in re.findall(r"\d+", fake_llm.requests[0]["messages"][0]["content"])} == {27, 31}
    # Every leaf string is a fixed label or tier.
    labels = set(phase_guide.PHASE_NAMES.values()) | {"moderate evidence", "strong evidence", "early sign",
                                                      "a walk", "strength training", "social plans"}
    for phase in sent["phases"]:
        assert phase["phase"] in labels
        for item in phase["tends_to_go_well"]:
            assert item["strategy"] in labels and item["evidence"] in labels


# --- validation ----------------------------------------------------------------------

def test_a_good_reply_is_shown_and_stored(conn, user, fake_llm):
    fake_llm.reply = GOOD_REPLY
    guide = generate(conn, user)
    assert guide.source == "llm" and guide.sections[0][1].startswith("In your data")
    assert phase_guide.stored(conn, user, CYCLE).sections == guide.sections


def test_once_per_completed_cycle(conn, user, fake_llm):
    fake_llm.reply = GOOD_REPLY
    generate(conn, user)
    generate(conn, user)
    assert len(fake_llm.requests) == 1
    phase_guide.generate(conn, user, FINDINGS, RANGE, date(2026, 10, 2), gate_open=True)
    assert len(fake_llm.requests) == 2  # a new completed cycle may get a new guide


def _reply(**changes):
    reply = json.loads(json.dumps(GOOD_REPLY))
    for i, text in changes.get("texts", {}).items():
        reply["phases"][i]["text"] = text
    if "cycle_sentence" in changes:
        reply["cycle_sentence"] = changes["cycle_sentence"]
    if "phases" in changes:
        reply["phases"] = changes["phases"]
    return reply


@pytest.mark.parametrize("reply", [
    # names a strategy that wasn't supplied for that phase
    _reply(texts={2: "Yoga tends to go well in your luteal phase."}),
    _reply(texts={0: "A walk and some yoga tend to go well on period days."}),
    # medical / hormonal / causal / instruction wording
    _reply(texts={0: "Walks tend to ease symptoms on period days."}),
    _reply(texts={1: "Strength training tends to go well as your estrogen rises."}),
    _reply(texts={1: "You should do strength training — it tends to go well."}),
    _reply(texts={1: "Your creativity peaks here; strength training tends to go well."}),
    # findings without associative wording
    _reply(texts={0: "Walking is great on period days."}),
    # a number that wasn't supplied
    _reply(cycle_sentence="Your cycles have usually run 28 days."),
    # structure
    _reply(phases=GOOD_REPLY["phases"][:2]),
    {"phases": "none", "cycle_sentence": "x"},
    {},
])
def test_any_violation_rejects_the_reply_and_shows_the_template(conn, user, fake_llm, reply):
    fake_llm.reply = reply
    guide = generate(conn, user)
    assert guide.source == "template" and guide.notice
    assert phase_guide.stored(conn, user, CYCLE) is None


def test_template_lists_exactly_the_findings_and_passes_the_same_checks():
    guide = phase_guide.template(FINDINGS, RANGE)
    assert [s[0] for s in guide.sections] == ["Period days", "Follicular phase", "Luteal phase"]
    assert "a walk (moderate evidence)" in guide.sections[0][1]
    assert "strength training (strong evidence)" in guide.sections[1][1]
    for name, text in guide.sections:
        assert not wording.banned_words(text)
    assert phase_guide.validate(
        {"phases": [{"phase": n, "text": t} for n, t in guide.sections], "cycle_sentence": guide.cycle_sentence},
        FINDINGS, RANGE,
    ) is not None


# --- when it may run -------------------------------------------------------------------

def test_off_until_opt_in(conn, user, fake_llm):
    db.update_settings(conn, user, phase_guide_opt_in=False)
    fake_llm.reply = GOOD_REPLY
    assert generate(conn, user).source == "template"
    assert fake_llm.requests == []


def test_not_before_the_gate_and_not_on_hormonal_contraception(conn, user, fake_llm):
    fake_llm.reply = GOOD_REPLY
    assert generate(conn, user, gate_open=False).source == "template"
    db.update_settings(conn, user, hormonal_contraception=True)
    assert generate(conn, user).source == "template"
    assert fake_llm.requests == []


def test_demo_opts_in_per_tab_only(conn, fake_llm):
    demo = auth.signup(conn, "x@example.com", "password-123456", "Demo").id
    db.update_settings(conn, demo, is_demo=True)
    fake_llm.reply = GOOD_REPLY
    assert generate(conn, demo).source == "template"  # no tab opt-in
    assert generate(conn, demo, session_opt_in=True).source == "llm"


@pytest.mark.parametrize("status", [500, 401])
def test_provider_failure_shows_the_template(conn, user, fake_llm, status):
    fake_llm.status = status
    guide = generate(conn, user)
    assert guide.source == "template" and "couldn't be reached" in guide.notice


def test_no_key_shows_the_template_without_any_request(conn, user, fake_llm, monkeypatch):
    monkeypatch.delenv(llm.API_KEY_ENV)
    guide = generate(conn, user)
    assert guide.source == "template" and fake_llm.requests == []


def test_cap_reached_shows_the_template(conn, user, fake_llm):
    fake_llm.raw_text = "not json"
    for _ in range(llm.DAILY_CAPS["phase_guide"]):
        generate(conn, user)
    fake_llm.raw_text = None
    fake_llm.reply = GOOD_REPLY
    guide = generate(conn, user)
    assert guide.source == "template" and "limit" in guide.notice
    assert len(fake_llm.requests) == 3


def test_ordinary_words_arent_mistaken_for_strategies():
    assert wording.strategies_mentioned("Your cycles have usually run between 27 and 31 days.") == set()
    assert wording.strategies_mentioned("You went for a run.") == {"cardio"}
