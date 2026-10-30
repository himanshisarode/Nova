"""Partner sharing: invite codes, one-way read-only links, revocation.

The inviter (user_id) shares their data; whoever redeems the code
(partner_user_id) becomes a read-only viewer. Two people who want to see
each other's data make two links. Codes are single-use and expire 48
hours after creation if unused.

Read-only is enforced by the database, not the UI: a PartnerView reads
through its own connection opened with SQLite's mode=ro and query_only,
so any write through it fails no matter what code tries it. It re-checks
the link on every read, so revoking takes effect on the partner's very
next request. It exposes only what SPEC.md allows a partner to see —
cycles (for the dashboard and Cycle Trends) and period predictions —
never raw daily logs or the remedy log.
"""
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import db
import predict

INVITE_LIFETIME = timedelta(hours=48)
# No 0/O or 1/I/L, so a code read aloud or retyped can't be misread.
CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


class InviteError(ValueError):
    """An invite couldn't be created or redeemed; the message is user-safe."""


class PartnerAccessError(PermissionError):
    """The viewer has no active link to this user's data."""


@dataclass(frozen=True)
class PartnerLink:
    id: int
    owner_id: int  # whose data is shared (the inviter)
    viewer_id: int | None  # who can see it (the invitee); None until redeemed
    invite_code: str
    status: str
    created_at: datetime
    expires_at: datetime
    accepted_at: datetime | None
    revoked_at: datetime | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def _parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def normalize_code(code: str) -> str:
    """Accept codes typed with spaces, dashes, or lowercase letters."""
    return "".join(ch for ch in code.upper() if ch.isalnum())


def format_code(code: str) -> str:
    """ABCD-EFGH, for display."""
    return f"{code[:4]}-{code[4:]}"


_LINK_COLUMNS = (
    "id, user_id, partner_user_id, invite_code, status, created_at, expires_at,"
    " accepted_at, revoked_at"
)


def _link(row) -> PartnerLink:
    link_id, owner, viewer, code, status, created, expires, accepted, revoked = row
    return PartnerLink(
        link_id, owner, viewer, code, status,
        _parse(created), _parse(expires), _parse(accepted), _parse(revoked),
    )


def create_invite(conn: sqlite3.Connection, owner_id: int, now: datetime | None = None) -> PartnerLink:
    """A new single-use code that lets someone view `owner_id`'s data."""
    now = now or _now()
    if db.get_settings(conn, owner_id).is_demo:
        raise InviteError("The demo account holds sample data and can't be shared.")
    for _ in range(5):  # a collision is astronomically unlikely; retry anyway
        code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
        try:
            with conn:
                cur = conn.execute(
                    "INSERT INTO partner_links (user_id, invite_code, status, created_at, expires_at)"
                    " VALUES (?, ?, 'pending', ?, ?)",
                    (owner_id, code, _iso(now), _iso(now + INVITE_LIFETIME)),
                )
            return get_link(conn, cur.lastrowid)
        except sqlite3.IntegrityError as exc:
            if "invite_code" not in str(exc):
                raise
    raise RuntimeError("could not generate a unique invite code")


def redeem_invite(
    conn: sqlite3.Connection, viewer_id: int, code: str, now: datetime | None = None
) -> PartnerLink:
    """Use a code: `viewer_id` becomes a read-only viewer of the inviter's data."""
    now = now or _now()
    row = conn.execute(
        f"SELECT {_LINK_COLUMNS} FROM partner_links WHERE invite_code = ?", (normalize_code(code),)
    ).fetchone()
    if row is None:
        raise InviteError("That code doesn't match any invite.")
    link = _link(row)
    if link.status != "pending":
        raise InviteError("That code has already been used or cancelled.")
    if now >= link.expires_at:
        with conn:
            conn.execute(
                "UPDATE partner_links SET status = 'expired' WHERE id = ? AND status = 'pending'",
                (link.id,),
            )
        raise InviteError("That code has expired — invite codes last 48 hours.")
    if link.owner_id == viewer_id:
        raise InviteError("That's your own invite code — share it with your partner instead.")
    if db.get_settings(conn, viewer_id).is_demo or db.get_settings(conn, link.owner_id).is_demo:
        raise InviteError("The demo account can't be linked with real accounts.")
    if viewer_can_see(conn, viewer_id, link.owner_id):
        raise InviteError("You can already see this person's data.")

    with conn:
        # The status check in the WHERE makes this the single point where a
        # code is consumed: a second redemption racing this one updates nothing.
        cur = conn.execute(
            "UPDATE partner_links SET partner_user_id = ?, status = 'accepted', accepted_at = ?"
            " WHERE id = ? AND status = 'pending'",
            (viewer_id, _iso(now), link.id),
        )
    if cur.rowcount != 1:
        raise InviteError("That code has already been used or cancelled.")
    return get_link(conn, link.id)


def revoke(conn: sqlite3.Connection, owner_id: int, link_id: int, now: datetime | None = None) -> None:
    """End a link (or cancel an unused code). Only the owner can revoke."""
    now = now or _now()
    with conn:
        cur = conn.execute(
            "UPDATE partner_links SET status = 'revoked', revoked_at = ?"
            " WHERE id = ? AND user_id = ? AND status IN ('pending', 'accepted')",
            (_iso(now), link_id, owner_id),
        )
    if cur.rowcount != 1:
        raise InviteError("There's no active link or invite to revoke there.")


def get_link(conn: sqlite3.Connection, link_id: int) -> PartnerLink:
    return _link(
        conn.execute(f"SELECT {_LINK_COLUMNS} FROM partner_links WHERE id = ?", (link_id,)).fetchone()
    )


def links_for(conn: sqlite3.Connection, user_id: int) -> list[PartnerLink]:
    """Every link where the user is owner or viewer, newest first — for settings.

    Revoked and expired links are included (with their dates) so the
    settings page can decide how to show history; see SPEC.md Open Questions.
    """
    return [
        _link(row) for row in conn.execute(
            f"SELECT {_LINK_COLUMNS} FROM partner_links"
            " WHERE user_id = ? OR partner_user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id, user_id),
        )
    ]


def viewer_can_see(conn: sqlite3.Connection, viewer_id: int, owner_id: int) -> bool:
    """True if there's an accepted, unrevoked link from owner to viewer."""
    return conn.execute(
        "SELECT 1 FROM partner_links"
        " WHERE user_id = ? AND partner_user_id = ? AND status = 'accepted'",
        (owner_id, viewer_id),
    ).fetchone() is not None


def _read_only_connection(path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


class PartnerView:
    """What a linked partner may see of the owner's data — read-only.

    Open with `PartnerView(db_path, viewer_id, owner_id)`; raises
    PartnerAccessError if there's no active link, and again on any read
    after the link is revoked.
    """

    def __init__(self, db_path: Path | str, viewer_id: int, owner_id: int) -> None:
        self._conn = _read_only_connection(db_path)
        self.viewer_id = viewer_id
        self.owner_id = owner_id
        self._check_access()

    def _check_access(self) -> None:
        if not viewer_can_see(self._conn, self.viewer_id, self.owner_id):
            raise PartnerAccessError("This view is no longer shared with you.")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "PartnerView":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- the only reads a partner gets -----------------------------------------

    def cycles(self) -> list[db.Cycle]:
        """Completed cycles — for the dashboard and Cycle Trends."""
        self._check_access()
        return db.get_cycles(self._conn, self.owner_id)

    def last_period_start(self) -> date | None:
        self._check_access()
        starts = db.get_period_starts(self._conn, self.owner_id)
        return starts[-1] if starts else None

    def simple_prediction(self) -> predict.SimplePrediction | predict.NotEnoughData:
        return self._predict(predict.simple_prediction)

    def honest_prediction(self) -> predict.HonestPrediction | predict.NotEnoughData:
        return self._predict(predict.honest_prediction)

    def _predict(self, fn):
        lengths = [c.length for c in self.cycles()]
        last = self.last_period_start()
        if last is None:
            return predict.NotEnoughData(have=0)
        return fn(lengths, last)
