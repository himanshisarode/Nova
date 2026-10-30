"""Phase 13: demo mode (spec.md Feature 21) — also the end-to-end fixture."""
from datetime import date

import pytest

import auth
import db
import demo
import gate
import partner
import phases
import whatworks

TODAY = date(2026, 10, 30)


@pytest.fixture
def conn(tmp_path):
    conn = db.connect(tmp_path / "nova.db")
    yield conn
    conn.close()


@pytest.fixture
def demo_user(conn):
    return demo.ensure_demo(conn, TODAY)


def test_demo_has_over_8_months_and_passes_the_gate(conn, demo_user):
    logs = db.get_logs(conn, demo_user.id)
    assert (TODAY - logs[0].date).days >= 243  # 8 months
    assert logs[-1].date == TODAY
    assert len(db.get_cycles(conn, demo_user.id)) == demo.DEMO_CYCLES
    assert gate.gate_status([e.date for e in logs], demo.DEMO_CYCLES, TODAY).open


def test_end_to_end_the_planted_effects_are_found(conn, demo_user):
    logs = db.get_logs(conn, demo_user.id)
    starts = db.get_period_starts(conn, demo_user.id)
    results = whatworks.analyse(whatworks.rated_days(starts, logs))
    found = {(r.bucket, r.strategy) for r in results if r.verdict == "tends_to_go_well"}
    assert set(demo.PLANTED) <= found
    assert found == set(demo.PLANTED)  # and nothing else, for this seed


def test_demo_is_labelled_and_flagged(conn, demo_user):
    assert demo_user.display_name == "Demo (sample data)"
    assert demo_user.email == "demo@nova.invalid"
    assert demo.is_demo(conn, demo_user.id)
    assert "Demo data" in demo.BANNER


def test_demo_has_no_usable_password(conn, demo_user):
    for guess in ("", "demo", "password", "demo@nova.invalid"):
        assert auth.login(conn, demo.DEMO_EMAIL, guess) is None


def test_demo_cannot_save_logs_or_remedies(conn, demo_user):
    with pytest.raises(db.DemoReadOnly):
        db.save_log(conn, demo_user.id, db.LogEntry(TODAY, flow="heavy"))
    with pytest.raises(db.DemoReadOnly):
        db.save_logs(conn, demo_user.id, [db.LogEntry(TODAY)])
    with pytest.raises(db.DemoReadOnly):
        db.delete_log(conn, demo_user.id, TODAY)
    with pytest.raises(db.DemoReadOnly):
        db.add_remedy(conn, demo_user.id, TODAY, "cramps", "tea", 3)


def test_demo_cannot_share_or_view_and_real_accounts_cant_link_to_it(conn, demo_user):
    real = auth.signup(conn, "maya@example.com", "password-123456", "Maya").id
    with pytest.raises(partner.InviteError):
        partner.create_invite(conn, demo_user.id)
    code = partner.create_invite(conn, real).invite_code
    with pytest.raises(partner.InviteError):
        partner.redeem_invite(conn, demo_user.id, code)
    assert not partner.viewer_can_see(conn, demo_user.id, real)


def test_signup_refuses_the_reserved_domain(conn):
    with pytest.raises(auth.SignupError, match="reserved"):
        auth.signup(conn, "someone@nova.invalid", "password-123456", "Someone")
    with pytest.raises(auth.SignupError):
        auth.signup(conn, "DEMO@Nova.Invalid", "password-123456", "Someone")


def test_reseeding_moves_the_demo_to_today_and_touches_nobody_else(conn, demo_user):
    real = auth.signup(conn, "maya@example.com", "password-123456", "Maya").id
    db.save_log(conn, real, db.LogEntry(TODAY, flow="light", day_rating=4))
    later = date(2026, 11, 5)
    again = demo.ensure_demo(conn, later)
    assert again.id == demo_user.id
    assert db.get_logs(conn, demo_user.id)[-1].date == later
    assert db.get_log(conn, real, TODAY).day_rating == 4
    assert conn.execute("SELECT COUNT(*) FROM users").fetchone() == (2,)


def test_replace_demo_logs_refuses_real_accounts(conn):
    real = auth.signup(conn, "maya@example.com", "password-123456", "Maya").id
    with pytest.raises(PermissionError):
        db.replace_demo_logs(conn, real, [])


def test_demo_current_cycle_has_a_phase(conn, demo_user):
    starts = db.get_period_starts(conn, demo_user.id)
    logs = db.get_logs(conn, demo_user.id)
    c = phases.current_cycle(starts, [e.date for e in logs if e.flow in db.BLEEDING_FLOWS],
                             [x.length for x in db.get_cycles(conn, demo_user.id)], TODAY)
    assert c.day == demo.OPEN_CYCLE_DAY and c.enough_data
