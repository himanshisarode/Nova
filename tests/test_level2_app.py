"""Phase 15: the Level 2 pages in the real app (Streamlit AppTest)."""
from datetime import date, timedelta

import pytest

import auth
import db
import demo
import export
import partner
import phase_guide
import simulate
import theme
from tests.test_app import app, goto, texts
from tests.ui_checks import card, card_has_disclaimer, footer_has_disclaimer

LEVEL2_PAGES = ("My phases", "Plan my week")
PHASE_WORDS = ("follicular", "luteal", "ovulation", "phase")


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "nova.db"
    monkeypatch.setenv("NOVA_DB_PATH", str(path))
    return path


@pytest.fixture
def conn(db_path):
    conn = db.connect(db_path)
    yield conn
    conn.close()


def seed_level2(conn, email="maya@example.com", n_cycles=8, seed_=5):
    """A real user past the gate, with ratings and strategies; open cycle
    started 10 days ago."""
    user = auth.signup(conn, email, "password-maya-1", "Maya")
    h = simulate.simulate_history(seed_, n_cycles=n_cycles, irregular_rate=0.0)
    shift = (date.today() - timedelta(days=10)) - h.starts[-1]
    logs = simulate.with_strategies(h, seed_, {("follicular", "strength"): 1.2})
    db.save_logs(conn, user.id, [
        db.LogEntry(e.date + shift, e.flow, e.mood, e.symptoms, e.poor_sleep, e.high_stress,
                    e.travel, e.day_rating, e.energy, e.strategies) for e in logs])
    return user


def demo_app(conn):
    return app(demo.ensure_demo(conn))


# --- every page, every kind of user --------------------------------------------------

@pytest.mark.parametrize("page", LEVEL2_PAGES)
def test_level2_pages_render_for_a_brand_new_user(db_path, conn, page):
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    at = goto(app(user), page)
    assert footer_has_disclaimer(at)


@pytest.mark.parametrize("page", ("Today", "Home", *LEVEL2_PAGES, "Insights", "Settings"))
def test_demo_banner_on_every_page(db_path, conn, page):
    at = goto(demo_app(conn), page)
    assert demo.BANNER in texts(at)
    assert footer_has_disclaimer(at)


# --- decision (c): no phase on the logging screen --------------------------------------

def test_today_page_never_names_a_phase(db_path, conn):
    at = goto(app(seed_level2(conn)), "Today")
    for word in PHASE_WORDS:
        assert word not in texts(at).lower(), word
    assert card(at, "log") is not None


# --- the gate ------------------------------------------------------------------------------

def test_before_the_gate_only_progress_and_the_tracker(db_path, conn, fake_llm):
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    db.save_log(conn, user.id, db.LogEntry(date.today() - timedelta(days=3), flow="heavy", day_rating=4))
    for page in LEVEL2_PAGES:
        at = goto(app(user), page)
        assert card(at, "gate") is not None
        assert "of 180" in texts(at) and "of 4" in texts(at) and "of 90" in texts(at)
        for hidden in ("what-works", "phase-guide", "week"):
            with pytest.raises(AssertionError):
                card(at, hidden)
    assert fake_llm.requests == []


def test_past_the_gate_the_findings_show_with_the_disclaimer(db_path, conn):
    at = goto(demo_app(conn), "My phases")
    assert "tended to be rated higher" in texts(at)
    for name in ("phase-tracker", "what-works", "phase-guide"):
        assert card_has_disclaimer(at, name), name
    assert "not causes" in texts(at)


def test_plan_my_week_template_without_opt_in(db_path, conn, fake_llm):
    at = goto(demo_app(conn), "Plan my week")
    assert card_has_disclaimer(at, "week")
    assert "turn on Plan my week in Settings" in texts(at)
    assert fake_llm.requests == []


# --- hormonal contraception (decision (d)) ---------------------------------------------

def test_hormonal_contraception_shows_the_caveat_and_switches_off_the_plan(db_path, conn, fake_llm):
    user = seed_level2(conn)
    db.update_settings(conn, user.id, hormonal_contraception=True, phase_guide_opt_in=True, week_fit_opt_in=True)
    at = goto(app(user), "My phases")
    assert "hormonal contraception" in " ".join(i.value for i in at.info)
    for hidden in ("what-works", "phase-guide", "gate"):
        with pytest.raises(AssertionError):
            card(at, hidden)
    at = goto(app(user), "Plan my week")
    assert card(at, "week-off") is not None
    assert fake_llm.requests == []


# --- the LLM features through the UI ------------------------------------------------------

GOOD_GUIDE = {
    "phases": [
        {"phase": "Period days", "text": "A walk tends to go well for you on period days."},
        {"phase": "Follicular phase", "text": "Strength training tends to go well for you here."},
        {"phase": "Luteal phase", "text": "An early night tends to go well for you in this phase."},
    ],
    "cycle_sentence": "placeholder",
}


def test_demo_visitor_opts_in_per_tab_and_gets_a_written_guide(db_path, conn, fake_llm):
    at = goto(demo_app(conn), "Settings")
    at.toggle(key="w_demo_opt_in_phase_guide").set_value(True).run()  # app.DEMO_OPT_IN
    lengths = [c.length for c in db.get_cycles(conn, demo.demo_user_id(conn))][-12:]
    fake_llm.reply = dict(GOOD_GUIDE, cycle_sentence=f"Your cycles have run between {min(lengths)} and {max(lengths)} days.")
    goto(at, "My phases")
    at.button(key="write_guide").click().run()
    assert not at.exception, at.exception
    assert len(fake_llm.requests) == 1
    assert "Strength training tends to go well for you here." in texts(at)
    # The shared demo account itself was never opted in.
    assert not db.get_settings(conn, demo.demo_user_id(conn)).phase_guide_opt_in


def test_settings_save_luteal_and_opt_ins(db_path, conn):
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    at = goto(app(user), "Settings")
    at.selectbox(key="setting_luteal").set_value(12)
    at.toggle(key="setting_week").set_value(True)
    next(b for b in at.button if b.label == "Save").click().run()
    assert not at.exception, at.exception
    s = db.get_settings(conn, user.id)
    assert s.luteal_days == 12 and s.week_fit_opt_in and not s.phase_guide_opt_in


# --- demo can't mix with real accounts, through the UI too ---------------------------------

def test_demo_settings_hide_sharing_and_delete(db_path, conn):
    at = goto(demo_app(conn), "Settings")
    for hidden in ("sharing", "my-data", "doctor"):
        with pytest.raises(AssertionError):
            card(at, hidden)


def test_try_the_demo_button_logs_into_the_demo(db_path, conn):
    at = app()
    at.button(key="try_demo").click().run()
    assert not at.exception
    assert at.session_state[auth.SESSION_KEY].email == demo.DEMO_EMAIL


# --- Level 2 data stays out of the doctor export and the partner view ---------------------

def test_level2_data_is_not_in_the_doctor_export(db_path, conn):
    user = seed_level2(conn)
    report = export.build_doctor_report(conn, user.id, months=None)
    csv_text = export.doctor_csv(report)
    from tests.test_export import _pdf_text

    pdf_text = _pdf_text(export.doctor_pdf(report))
    for text in (csv_text, pdf_text):
        low = text.lower()
        for word in ("rating", "energy", "strateg", "yoga", "journaling", "early_night", "early night",
                     "deep_focus", "social_plans", "follicular", "luteal", "phase guide"):
            assert word not in low, word


def test_partner_view_shows_no_level2_data(db_path, conn):
    owner = seed_level2(conn)
    viewer = auth.signup(conn, "bea@example.com", "password-bea-12", "Bea")
    partner.redeem_invite(conn, viewer.id, partner.create_invite(conn, owner.id).invite_code)
    at = goto(app(viewer), "Shared with me")
    low = texts(at).lower()
    for word in ("tended to be rated", "follicular", "luteal", "phase guide", "strength training", "yoga"):
        assert word not in low, word


def test_level2_data_is_gone_after_delete_all(db_path, conn):
    user = seed_level2(conn)
    with conn:
        conn.execute("INSERT INTO phase_guide VALUES (?, '2026-01-01', ?, 'now')",
                     (user.id, '{"sections": [["x", "zebra-guide-token"]]}'))
        conn.execute("INSERT INTO llm_usage VALUES (?, '2026-10-30', 'week_fit', 4)", (user.id,))
    db.update_settings(conn, user.id, luteal_days=13, week_fit_opt_in=True)
    db.delete_account(conn, user.id, "maya@example.com")
    conn.commit()
    raw = db_path.read_bytes()
    assert b"zebra-guide-token" not in raw
    for table in ("daily_strategy", "user_settings", "phase_guide", "llm_usage"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone() == (0,), table
