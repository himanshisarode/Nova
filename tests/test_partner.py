"""Phase 4: invite codes, one-way read-only links, immediate revocation."""
import sqlite3
from datetime import date, datetime, timedelta, timezone

import pytest

import auth
import db
import partner
import predict

T0 = datetime(2026, 10, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "nova.db"


@pytest.fixture
def conn(db_path):
    conn = db.connect(db_path)
    yield conn
    conn.close()


@pytest.fixture
def users(conn):
    """owner (shares data), viewer (invited partner), other (a third person)."""
    return tuple(
        auth.signup(conn, f"{name}@example.com", f"password-{name}", name).id
        for name in ("owner", "viewer", "other")
    )


@pytest.fixture
def owner_data(conn, users):
    """Owner has 4 completed cycles (28, 30, 29, 28 days) plus an open one."""
    owner = users[0]
    start = date(2026, 1, 1)
    for length in (28, 30, 29, 28, None):
        for k in range(4):
            db.save_log(conn, owner, db.LogEntry(
                start + timedelta(days=k), flow="medium", mood=2,
                symptoms=frozenset({"cramps"}), high_stress=True,
            ))
        if length:
            start += timedelta(days=length)
    return owner


def linked(conn, owner, viewer, now=T0):
    invite = partner.create_invite(conn, owner, now=now)
    return partner.redeem_invite(conn, viewer, invite.invite_code, now=now)


# --- invites ------------------------------------------------------------------

def test_invite_code_shape_and_expiry(conn, users):
    invite = partner.create_invite(conn, users[0], now=T0)
    assert len(invite.invite_code) == partner.CODE_LENGTH
    assert set(invite.invite_code) <= set(partner.CODE_ALPHABET)
    assert invite.status == "pending" and invite.viewer_id is None
    assert invite.expires_at == T0 + timedelta(hours=48)


def test_redeeming_links_viewer_to_owner(conn, users):
    owner, viewer, _ = users
    link = linked(conn, owner, viewer)
    assert (link.owner_id, link.viewer_id, link.status) == (owner, viewer, "accepted")
    assert link.accepted_at == T0


def test_code_typed_loosely_still_works(conn, users):
    owner, viewer, _ = users
    code = partner.create_invite(conn, owner, now=T0).invite_code
    messy = " " + partner.format_code(code).lower() + " "
    assert partner.redeem_invite(conn, viewer, messy, now=T0).status == "accepted"


def test_code_is_single_use(conn, users):
    owner, viewer, other = users
    code = partner.create_invite(conn, owner, now=T0).invite_code
    partner.redeem_invite(conn, viewer, code, now=T0)
    with pytest.raises(partner.InviteError, match="already been used"):
        partner.redeem_invite(conn, other, code, now=T0)
    assert not partner.viewer_can_see(conn, other, owner)


def test_code_expires_after_48_hours(conn, users):
    owner, viewer, other = users
    fresh = partner.create_invite(conn, owner, now=T0).invite_code
    stale = partner.create_invite(conn, owner, now=T0).invite_code

    just_in_time = T0 + timedelta(hours=48) - timedelta(seconds=1)
    assert partner.redeem_invite(conn, viewer, fresh, now=just_in_time).status == "accepted"

    with pytest.raises(partner.InviteError, match="expired"):
        partner.redeem_invite(conn, other, stale, now=T0 + timedelta(hours=48))
    assert not partner.viewer_can_see(conn, other, owner)
    assert [l.status for l in partner.links_for(conn, other)] == []
    statuses = {l.invite_code: l.status for l in partner.links_for(conn, owner)}
    assert statuses[stale] == "expired"


@pytest.mark.parametrize("code, message", [("ZZZZZZZZ", "doesn't match"), ("", "doesn't match")])
def test_unknown_code_rejected(conn, users, code, message):
    with pytest.raises(partner.InviteError, match=message):
        partner.redeem_invite(conn, users[1], code, now=T0)


def test_cannot_redeem_own_code(conn, users):
    code = partner.create_invite(conn, users[0], now=T0).invite_code
    with pytest.raises(partner.InviteError, match="your own"):
        partner.redeem_invite(conn, users[0], code, now=T0)


def test_cannot_link_twice_in_the_same_direction(conn, users):
    owner, viewer, _ = users
    linked(conn, owner, viewer)
    second = partner.create_invite(conn, owner, now=T0).invite_code
    with pytest.raises(partner.InviteError, match="already see"):
        partner.redeem_invite(conn, viewer, second, now=T0)


# --- one-way ------------------------------------------------------------------

def test_link_is_one_way(conn, db_path, users, owner_data):
    owner, viewer, _ = users
    linked(conn, owner, viewer)
    assert partner.viewer_can_see(conn, viewer, owner)
    assert not partner.viewer_can_see(conn, owner, viewer)
    with pytest.raises(partner.PartnerAccessError):
        partner.PartnerView(db_path, viewer_id=owner, owner_id=viewer)


def test_mutual_visibility_takes_two_links(conn, users):
    a, b, _ = users
    linked(conn, a, b)
    linked(conn, b, a)
    assert partner.viewer_can_see(conn, b, a) and partner.viewer_can_see(conn, a, b)


def test_unlinked_user_has_no_access(db_path, conn, users, owner_data):
    with pytest.raises(partner.PartnerAccessError):
        partner.PartnerView(db_path, viewer_id=users[2], owner_id=users[0])


# --- what the partner sees ----------------------------------------------------

def test_partner_sees_owners_cycles_and_predictions(conn, db_path, users, owner_data):
    owner, viewer, _ = users
    linked(conn, owner, viewer)
    lengths = [c.length for c in db.get_cycles(conn, owner)]
    last = db.get_period_starts(conn, owner)[-1]

    with partner.PartnerView(db_path, viewer, owner) as view:
        assert view.cycles() == db.get_cycles(conn, owner)
        assert [c.length for c in view.cycles()] == [28, 30, 29, 28]
        assert view.last_period_start() == last
        assert view.simple_prediction() == predict.simple_prediction(lengths, last)
        assert view.honest_prediction() == predict.honest_prediction(lengths, last)


def test_partner_view_exposes_nothing_beyond_the_allowed_reads():
    # SPEC.md: dashboard, Cycle Trends, predictions only. A new public
    # method on PartnerView has to be added here deliberately.
    public = {name for name in dir(partner.PartnerView) if not name.startswith("_")}
    assert public == {
        "cycles", "last_period_start", "simple_prediction", "honest_prediction", "close",
    }


def test_partner_results_contain_no_raw_logs(conn, db_path, users, owner_data):
    owner, viewer, _ = users
    linked(conn, owner, viewer)
    with partner.PartnerView(db_path, viewer, owner) as view:
        results = [view.cycles(), view.last_period_start(),
                   view.simple_prediction(), view.honest_prediction()]
    flat = [x for r in results for x in (r if isinstance(r, list) else [r])]
    assert not any(isinstance(x, db.LogEntry) for x in flat)
    # Nothing logged-day-specific leaks through repr either (moods,
    # symptoms, lifestyle tags from owner_data).
    text = repr(results)
    for leaked in ("cramps", "high_stress", "mood"):
        assert leaked not in text


# --- read-only, enforced by the database --------------------------------------

@pytest.mark.parametrize(
    "write",
    [
        lambda c, owner: db.save_log(c, owner, db.LogEntry(date(2026, 6, 1), flow="heavy")),
        lambda c, owner: db.delete_log(c, owner, date(2026, 1, 1)),
        lambda c, owner: c.execute("UPDATE daily_log SET mood = 5"),
        lambda c, owner: c.execute("DELETE FROM cycle"),
        lambda c, owner: c.execute("UPDATE partner_links SET status = 'accepted'"),
    ],
)
def test_partner_connection_cannot_write(conn, db_path, users, owner_data, write):
    # Even code that reaches past the view's API to its connection can't
    # write: the connection itself is read-only.
    owner, viewer, _ = users
    linked(conn, owner, viewer)
    before = (db.get_logs(conn, owner), db.get_cycles(conn, owner))
    with partner.PartnerView(db_path, viewer, owner) as view:
        with pytest.raises(sqlite3.OperationalError, match="readonly|read-only|query_only|query-only"):
            write(view._conn, owner)
    assert (db.get_logs(conn, owner), db.get_cycles(conn, owner)) == before


# --- revoking -----------------------------------------------------------------

def test_revoke_cuts_off_an_already_open_view_immediately(conn, db_path, users, owner_data):
    owner, viewer, _ = users
    link = linked(conn, owner, viewer)
    view = partner.PartnerView(db_path, viewer, owner)
    try:
        assert view.cycles()  # works while linked
        partner.revoke(conn, owner, link.id, now=T0 + timedelta(days=3))
        for read in (view.cycles, view.last_period_start,
                     view.simple_prediction, view.honest_prediction):
            with pytest.raises(partner.PartnerAccessError):
                read()
    finally:
        view.close()
    with pytest.raises(partner.PartnerAccessError):
        partner.PartnerView(db_path, viewer, owner)


def test_revoke_keeps_a_dated_record(conn, users):
    owner, viewer, _ = users
    link = linked(conn, owner, viewer)
    partner.revoke(conn, owner, link.id, now=T0 + timedelta(days=3))
    [record] = partner.links_for(conn, owner)
    assert record.status == "revoked"
    assert (record.accepted_at, record.revoked_at) == (T0, T0 + timedelta(days=3))


def test_only_the_owner_can_revoke(conn, users):
    owner, viewer, _ = users
    link = linked(conn, owner, viewer)
    with pytest.raises(partner.InviteError):
        partner.revoke(conn, viewer, link.id, now=T0)
    assert partner.viewer_can_see(conn, viewer, owner)


def test_cancelled_invite_cannot_be_redeemed(conn, users):
    owner, viewer, _ = users
    invite = partner.create_invite(conn, owner, now=T0)
    partner.revoke(conn, owner, invite.id, now=T0)
    with pytest.raises(partner.InviteError, match="already been used or cancelled"):
        partner.redeem_invite(conn, viewer, invite.invite_code, now=T0)


def test_can_relink_after_revoking(conn, users):
    owner, viewer, _ = users
    partner.revoke(conn, owner, linked(conn, owner, viewer).id, now=T0)
    assert linked(conn, owner, viewer).status == "accepted"
    assert partner.viewer_can_see(conn, viewer, owner)


def test_revoking_twice_fails_cleanly(conn, users):
    owner, viewer, _ = users
    link = linked(conn, owner, viewer)
    partner.revoke(conn, owner, link.id, now=T0)
    with pytest.raises(partner.InviteError):
        partner.revoke(conn, owner, link.id, now=T0)
