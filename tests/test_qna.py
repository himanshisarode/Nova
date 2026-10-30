"""Phase 7 / Level 2: "Did You Know?" — 21 static entries in three
sections, rendered with no network."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import auth
import db
import qna_content

ROOT = Path(__file__).parent.parent


def test_exactly_21_entries_in_three_sections_with_question_and_answer():
    assert len(qna_content.QNA) == 21
    assert [(title, len(items)) for title, items in qna_content.SECTIONS] == [
        ("Cycle syncing", 3), ("Your cycle's phases", 6), ("Common questions", 12),
    ]
    assert qna_content.QNA == [i for _, items in qna_content.SECTIONS for i in items]
    for item in qna_content.QNA:
        assert set(item) == {"question", "answer"}
        assert item["question"].strip().endswith("?")
        assert len(item["answer"].strip()) > 80  # a real short paragraph


def test_questions_are_distinct():
    questions = [item["question"] for item in qna_content.QNA]
    assert len(set(questions)) == len(questions)


def test_content_never_claims_clinical_review():
    text = " ".join(i["question"] + " " + i["answer"] for i in qna_content.QNA).lower()
    for claim in ("expert-reviewed", "clinically reviewed", "reviewed by", "doctor-approved"):
        assert claim not in text


@pytest.fixture
def logged_in(tmp_path, monkeypatch):
    path = tmp_path / "nova.db"
    monkeypatch.setenv("NOVA_DB_PATH", str(path))
    conn = db.connect(path)
    user = auth.signup(conn, "a@example.com", "password-a-123", "A")
    conn.close()
    return user


def test_ranges_match_the_apps_own_numbers():
    # The irregularity flag uses FIGO's 24–38 days and the fertile window runs
    # 5 days before ovulation to 1 after; the Q&A must not say otherwise.
    text = " ".join(i["answer"] for i in qna_content.QNA)
    assert "21 or more than 35" not in text and "21–35" not in text
    assert "shorter than 24 or longer than 38 days" in text
    assert "five days before ovulation to a day after" in text


def test_page_renders_every_entry_with_the_label_and_no_network(logged_in, no_network):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90)
    at.session_state[auth.SESSION_KEY] = logged_in
    at.run()
    at.sidebar.radio(key="nav").set_value("Did You Know?").run()
    assert not at.exception

    assert [e.label for e in at.expander] == [i["question"] for i in qna_content.QNA]
    answers = [m.value for m in at.markdown]
    for item in qna_content.QNA:
        assert item["answer"] in answers
    labels = [c.value for c in at.caption if c.value == qna_content.EDUCATION_LABEL]
    assert len(labels) == len(qna_content.QNA)  # under every answer
    headings = [m.value for m in at.markdown if m.value.startswith("#### ")]
    assert headings == [f"#### {title}" for title, _ in qna_content.SECTIONS]
