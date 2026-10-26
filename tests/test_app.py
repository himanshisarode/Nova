"""Phase 8: the real app, driven through Streamlit's AppTest."""
from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import auth
import db
import partner
import simulate
from tests.ui_checks import card, card_has_disclaimer, footer_has_disclaimer

ROOT = Path(__file__).parent.parent
APP = str(ROOT / "app.py")


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


def seed(conn, email="maya@example.com", name="Maya", n_cycles=6, seed_=4):
    """A user whose open cycle started 10 days ago, after n completed cycles."""
    user = auth.signup(conn, email, "password-maya-1", name)
    h = simulate.simulate_history(seed_, n_cycles=n_cycles, irregular_rate=0.3)
    shift = (date.today() - timedelta(days=10)) - h.starts[-1]
    for entry in h.logs:
        db.save_log(conn, user.id, db.LogEntry(
            entry.date + shift, entry.flow, entry.mood, entry.symptoms,
            entry.poor_sleep, entry.high_stress, entry.travel,
        ))
    return user


def app(user=None) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=90)
    if user is not None:
        at.session_state[auth.SESSION_KEY] = user
    return at.run()


def goto(at: AppTest, page: str) -> AppTest:
    at.sidebar.radio(key="nav").set_value(page).run()
    assert not at.exception, at.exception
    return at


def texts(at: AppTest) -> str:
    parts = [m.value for m in at.markdown] + [c.value for c in at.caption]
    return "\n".join(parts)


# --- logging in ---------------------------------------------------------------

def test_anonymous_visitor_sees_login_with_footer(db_path):
    at = app()
    assert not at.exception
    assert [t.label for t in at.tabs] == ["Log in", "Create account"]
    assert footer_has_disclaimer(at)


def test_signup_logs_you_in(db_path, conn):
    at = app()
    at.text_input(key="signup_name").input("Maya")
    at.text_input(key="signup_email").input("maya@example.com")
    at.text_input(key="signup_password").input("password-maya-1")
    at.button[1].click().run()  # "Create account" (the second form's submit)
    assert not at.exception
    assert at.sidebar.radio(key="nav").value == "Today"
    assert auth.login(conn, "maya@example.com", "password-maya-1") is not None


def test_wrong_password_shows_a_friendly_error(db_path, conn):
    auth.signup(conn, "maya@example.com", "password-maya-1", "Maya")
    at = app()
    at.text_input(key="login_email").input("maya@example.com")
    at.text_input(key="login_password").input("not-the-password")
    at.button[0].click().run()
    assert "don't match" in at.error[0].value
    assert auth.SESSION_KEY not in at.session_state


# --- every page ---------------------------------------------------------------

PAGES = ("Today", "Home", "Cycle Trends", "Insights", "Did You Know?", "Shared with me", "Settings")


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_with_the_footer(db_path, conn, page):
    at = goto(app(seed(conn)), page)
    assert footer_has_disclaimer(at)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_for_a_brand_new_user(db_path, conn, page):
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    at = goto(app(user), page)
    assert footer_has_disclaimer(at)


# SPEC.md Phase 8 acceptance: features 1–7, 9, 10, 13, 14, 15, 16 reachable.
# Each maps to the page and card where it lives (9 and 13 are the login
# flow and the styling itself, covered by the tests above).
FEATURE_CARDS = {
    1: ("Today", "log"),
    2: ("Home", "prediction"),
    3: ("Home", "fertile"),
    4: ("Cycle Trends", "trend-length"),
    5: ("Insights", "flags"),
    6: ("Settings", "doctor"),
    7: ("Settings", "my-data"),
    10: ("Settings", "sharing"),
    14: ("Did You Know?", "qna-intro"),
    15: ("Insights", "links"),
    16: ("Insights", "remedies"),
}


@pytest.mark.parametrize("feature", sorted(FEATURE_CARDS))
def test_every_in_scope_feature_is_reachable(db_path, conn, feature):
    page, name = FEATURE_CARDS[feature]
    at = goto(app(seed(conn)), page)
    card(at, name)  # asserts the card exists exactly once


# --- the disclaimer next to every prediction and flag -------------------------

@pytest.mark.parametrize("page, name", [
    ("Home", "prediction"), ("Home", "fertile"),
    ("Cycle Trends", "trend-length"), ("Insights", "flags"),
])
@pytest.mark.parametrize("with_data", [True, False])
def test_disclaimer_in_every_prediction_and_flag_card(db_path, conn, page, name, with_data):
    user = seed(conn) if with_data else auth.signup(conn, "new@example.com", "password-new-1", "New")
    at = goto(app(user), page)
    assert card_has_disclaimer(at, name)


def test_disclaimer_in_partner_view(db_path, conn):
    owner = seed(conn)
    viewer = auth.signup(conn, "sam@example.com", "password-sam-1", "Sam")
    partner.redeem_invite(conn, viewer.id, partner.create_invite(conn, owner.id).invite_code)
    at = goto(app(viewer), "Shared with me")
    assert card_has_disclaimer(at, "partner-prediction")
    assert footer_has_disclaimer(at)


# --- what the pages actually show ---------------------------------------------

def test_home_shows_honest_range_then_simple_date(db_path, conn):
    at = goto(app(seed(conn)), "Home")
    assert "### Between " in texts(at)
    at.segmented_control(key="mode").set_value("Simple").run()
    assert "### Around " in texts(at)


def test_new_user_home_is_warm_not_empty(db_path, conn):
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    at = goto(app(user), "Home")
    html = " ".join(h.proto.body for h in at.get("html"))
    assert "Getting to know the rhythm" in html and "0 of 3 so far" in html


def test_today_form_saves_the_day_and_a_remedy(db_path, conn):
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    at = app(user)
    k = date.today().isoformat()
    at.selectbox(key=f"flow_{k}").select("heavy")
    at.multiselect(key=f"symptoms_{k}").select("cramps")
    at.checkbox(key=f"high_stress_{k}").check()
    at.selectbox(key=f"r_symptom_{k}").select("cramps")
    at.text_input(key=f"r_text_{k}").input("  Heat Pad ")
    at.slider(key=f"r_rating_{k}").set_value(4)
    at.button[0].click().run()
    assert not at.exception
    saved = db.get_log(conn, user.id, date.today())
    assert (saved.flow, saved.symptoms, saved.high_stress) == ("heavy", {"cramps"}, True)
    [entry] = db.get_remedies(conn, user.id)
    assert (entry.symptom, entry.remedy, entry.relief_rating) == ("cramps", "heat_pad", 4)


def test_today_form_prefills_an_existing_day(db_path, conn):
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    db.save_log(conn, user.id, db.LogEntry(date.today(), flow="light", mood=4))
    at = app(user)
    k = date.today().isoformat()
    assert at.selectbox(key=f"flow_{k}").value == "light"
    assert at.select_slider(key=f"mood_{k}").value == 4


def test_qna_page_says_content_is_coming(db_path, conn):
    # Until the wording is approved, qna_content.QNA is empty.
    at = goto(app(seed(conn)), "Did You Know?")
    assert any("These are being written" in h.proto.body for h in at.get("html"))


# --- partner flow through the UI ----------------------------------------------

def test_invite_redeem_view_and_revoke_through_the_ui(db_path, conn):
    owner = seed(conn)
    viewer = auth.signup(conn, "sam@example.com", "password-sam-1", "Sam")

    at_owner = goto(app(owner), "Settings")
    at_owner.button(key="new_invite").click().run()
    code = at_owner.session_state["last_invite"]

    at_viewer = goto(app(viewer), "Settings")
    at_viewer.text_input(key="redeem_code").input(partner.format_code(code).lower())
    [use] = [b for b in at_viewer.button if b.label == "Use code"]
    use.click().run()
    assert "Linked" in at_viewer.success[0].value

    at_viewer = goto(at_viewer, "Shared with me")
    shown = texts(at_viewer)
    assert "Maya's cycle, read-only" in shown
    assert "### Between " in shown
    # No daily-log details on the partner page.
    for private in ("cramps", "fatigue", "stress", "sleep", "mood", "heat"):
        assert private not in shown.lower()

    link = partner.links_for(conn, owner.id)[0]
    at_owner = goto(app(owner), "Settings")
    at_owner.button(key=f"revoke_{link.id}").click().run()
    at_viewer = goto(app(viewer), "Shared with me")
    assert any("Nothing shared with you yet" in h.proto.body for h in at_viewer.get("html"))


# --- delete account through the UI --------------------------------------------

def test_delete_needs_the_right_email_then_removes_everything(db_path, conn):
    user = seed(conn)
    at = goto(app(user), "Settings")
    at.text_input(key="delete_confirm").input("wrong@example.com")
    at.button(key="delete_account").click().run()
    assert "doesn't match" in at.error[0].value
    assert auth.get_user(conn, user.id) is not None

    at.text_input(key="delete_confirm").input("maya@example.com")
    at.button(key="delete_account").click().run()
    assert not at.exception
    assert auth.get_user(conn, user.id) is None
    assert db.get_logs(conn, user.id) == []
    assert "have been deleted" in at.success[0].value
    assert [t.label for t in at.tabs] == ["Log in", "Create account"]
