"""Phase 7: doctor export (CSV/PDF), export-my-data, delete-all-my-data."""
import io
import json
import re
import sqlite3
import zipfile
from datetime import date, timedelta

import pytest
from pypdf import PdfReader

import auth
import db
import export
import irregularity
import partner
import theme

TODAY = date(2026, 5, 20)
A_NAME = "Zephyrine Quillfeather"  # distinctive, so a raw-file grep can't false-match
A_EMAIL = "zephyrine@example.com"
A_PASSWORD = "lavender-moon-42"


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "nova.db"


@pytest.fixture
def conn(db_path):
    conn = db.connect(db_path)
    yield conn
    conn.close()


def log_cycles(conn, user_id, first_start, lengths, flows=("heavy", "heavy", "medium", "light", "light")):
    """A period at each start; every day tagged high stress with low mood,
    so the doctor export's exclusion of tags and mood can be checked."""
    start = first_start
    for i, length in enumerate([*lengths, None]):
        for k, flow in enumerate(flows):
            symptoms = {"cramps"} if k < 2 else set()
            if i == 0 and k == 2:
                symptoms.add("fatigue")
            db.save_log(conn, user_id, db.LogEntry(
                start + timedelta(days=k), flow=flow, mood=2,
                symptoms=frozenset(symptoms), high_stress=True, poor_sleep=True,
            ))
        if length:
            start += timedelta(days=length)


@pytest.fixture
def users(conn):
    a = auth.signup(conn, A_EMAIL, A_PASSWORD, A_NAME).id
    b = auth.signup(conn, "bea@example.com", "password-bea-1", "Bea").id
    # A: starts Jan 1, Jan 29, Feb 28, Mar 29, May 9 -> cycles 28, 30, 29, 41.
    # The 41 is irregular: usual = median(28, 30, 29) = 29, 12 over, above 38.
    log_cycles(conn, a, date(2026, 1, 1), [28, 30, 29, 41])
    log_cycles(conn, b, date(2026, 1, 10), [27, 27, 27], flows=("medium",) * 3)
    return a, b


# --- date range ---------------------------------------------------------------

@pytest.mark.parametrize(
    "day, months, expected",
    [
        (date(2026, 5, 31), 3, date(2026, 2, 28)),  # clamped to February's end
        (date(2024, 5, 29), 3, date(2024, 2, 29)),  # leap year
        (date(2026, 3, 15), 12, date(2025, 3, 15)),
        (date(2026, 1, 10), 1, date(2025, 12, 10)),  # across a year boundary
    ],
)
def test_months_before(day, months, expected):
    assert export.months_before(day, months) == expected


def test_report_range_filters_by_cycle_start(conn, users):
    a, _ = users
    # 3 months before May 20 is Feb 20: cycles starting Feb 28 and Mar 29.
    three = export.build_doctor_report(conn, a, months=3, today=TODAY)
    assert [r.start for r in three.rows] == [date(2026, 2, 28), date(2026, 3, 29)]
    assert len(export.build_doctor_report(conn, a, months=None, today=TODAY).rows) == 4


def test_irregularity_judged_against_full_history(conn, users):
    # In the 3-month report only 1 earlier cycle is in range, but the 41-day
    # cycle is still compared with all 3 cycles before it.
    a, _ = users
    last = export.build_doctor_report(conn, a, months=3, today=TODAY).rows[-1]
    assert last.irregular
    assert last.reason.startswith("12 days longer than your usual 29")


# --- report contents ----------------------------------------------------------

def test_cycle_rows_by_hand(conn, users):
    a, _ = users
    rows = export.build_doctor_report(conn, a, months=12, today=TODAY).rows
    assert [r.length for r in rows] == [28, 30, 29, 41]
    assert [r.period_days for r in rows] == [5, 5, 5, 5]
    assert {r.heaviest_flow for r in rows} == {"heavy"}
    assert [r.irregular for r in rows] == [False, False, False, True]
    assert rows[0].symptoms == {"cramps": 2, "fatigue": 1}
    assert rows[1].symptoms == {"cramps": 2}


def test_symptom_share(conn, users):
    a, _ = users
    report = export.build_doctor_report(conn, a, months=12, today=TODAY)
    assert report.symptom_share() == {"cramps": 1.0, "fatigue": 0.25}


def test_doctor_csv_exact(conn, users):
    a, _ = users
    csv_text = export.doctor_csv(export.build_doctor_report(conn, a, months=12, today=TODAY))
    assert csv_text.splitlines() == [
        "cycle_start,cycle_end,length_days,period_days,heaviest_flow,irregular,what_happened,symptoms",
        "2026-01-01,2026-01-28,28,5,heavy,no,,cramps:2; fatigue:1",
        "2026-01-29,2026-02-27,30,5,heavy,no,,cramps:2",
        "2026-02-28,2026-03-28,29,5,heavy,no,,cramps:2",
        "2026-03-29,2026-05-08,41,5,heavy,yes,"
        "12 days longer than your usual 29; longer than the 24–38 day range "
        "that's typical for adults,cramps:2",
    ]


def _pdf_text(pdf: bytes) -> str:
    text = " ".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)
    return re.sub(r"\s+", " ", text)


def test_doctor_pdf_contents(conn, users):
    a, _ = users
    pdf = export.doctor_pdf(export.build_doctor_report(conn, a, months=12, today=TODAY))
    assert pdf.startswith(b"%PDF")
    text = _pdf_text(pdf)
    assert A_NAME in text
    assert "Completed cycles 4" in text
    assert "28 / 41 days" in text  # shortest / longest
    assert "12 days longer than your usual 29" in text
    assert "cramps 100%" in text and "fatigue 25%" in text


def test_doctor_pdf_carries_the_disclaimer_on_every_page(conn, users):
    a, _ = users
    pdf = export.doctor_pdf(export.build_doctor_report(conn, a, months=12, today=TODAY))
    expected = re.sub(r"\s+", " ", theme.MEDICAL_DISCLAIMER)
    for page in PdfReader(io.BytesIO(pdf)).pages:
        assert expected in re.sub(r"\s+", " ", page.extract_text())


def test_doctor_pdf_with_no_cycles(conn):
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    pdf = export.doctor_pdf(export.build_doctor_report(conn, user.id, months=12, today=TODAY))
    assert "No completed cycles in this date range." in _pdf_text(pdf)


def test_doctor_export_leaves_out_excluded_details(conn, users):
    # SPEC: no email, mood, lifestyle tags, remedy log, SHAP, partner details.
    a, b = users
    partner.redeem_invite(conn, b, partner.create_invite(conn, a).invite_code)
    report = export.build_doctor_report(conn, a, months=12, today=TODAY)
    for text in (export.doctor_csv(report), _pdf_text(export.doctor_pdf(report))):
        lowered = text.lower()
        for banned in ("zephyrine@", "@example.com", "mood", "stress", "sleep", "travel",
                       "remedy", "partner", "bea", "associat", "because", "due to"):
            assert banned not in lowered, banned


def test_reason_text_describes_what_not_why():
    # Every reason the rule can produce, for every kind of flag.
    cycles_by_case = {
        "long vs usual": [29, 28, 30, 37],
        "short vs usual": [33, 34, 33, 25],
        "above range": [39],
        "below range": [23],
        "both": [29, 28, 30, 41],
    }
    labels = [label.lower() for label in irregularity.FEATURE_LABELS.values()]
    for lengths in cycles_by_case.values():
        starts = [date(2026, 1, 1)]
        for n in lengths:
            starts.append(starts[-1] + timedelta(days=n))
        reason = irregularity.assess_cycles(db.cycles_from_starts(starts))[-1].reason
        assert reason
        for word in labels + ["stress", "sleep", "travel", "mood", "symptom", "because", "due to"]:
            assert word not in reason.lower()


def test_doctor_export_contains_only_that_users_data(conn, users):
    a, _ = users
    csv_text = export.doctor_csv(export.build_doctor_report(conn, a, months=None, today=TODAY))
    assert "2026-01-10" not in csv_text  # Bea's first period start
    assert "Bea" not in _pdf_text(export.doctor_pdf(export.build_doctor_report(conn, a, today=TODAY)))


# --- export my data -----------------------------------------------------------

def _zip(conn, user_id) -> dict[str, str]:
    with zipfile.ZipFile(io.BytesIO(export.export_my_data(conn, user_id))) as zf:
        return {name: zf.read(name).decode("utf-8") for name in zf.namelist()}


def test_export_my_data_contains_everything(conn, users):
    a, b = users
    link = partner.redeem_invite(conn, b, partner.create_invite(conn, a).invite_code)
    files = _zip(conn, a)
    assert set(files) == {
        "account.json", "daily_log.csv", "cycles.csv", "partner_links.csv", "remedy_log.csv",
    }

    account = json.loads(files["account.json"])
    assert account == {"email": A_EMAIL, "display_name": A_NAME,
                       "created_at": auth.get_user(conn, a).created_at}

    log_lines = files["daily_log.csv"].splitlines()
    assert log_lines[0] == "date,flow,mood,symptoms,poor_sleep,high_stress,travel"
    assert len(log_lines) - 1 == len(db.get_logs(conn, a)) == 25
    assert log_lines[1] == "2026-01-01,heavy,2,cramps,1,1,0"
    assert files["cycles.csv"].splitlines()[1:] == [
        "2026-01-01,2026-01-28,28", "2026-01-29,2026-02-27,30",
        "2026-02-28,2026-03-28,29", "2026-03-29,2026-05-08,41",
    ]
    links = files["partner_links.csv"].splitlines()
    assert links[1].startswith("sharing_with,Bea,accepted,")
    assert link.invite_code not in files["partner_links.csv"]


def test_export_my_data_has_no_secrets_and_no_one_elses_data(conn, users):
    a, _ = users
    stored_hash = conn.execute("SELECT password_hash FROM users WHERE id = ?", (a,)).fetchone()[0]
    everything = "".join(_zip(conn, a).values())
    assert stored_hash not in everything and "password" not in everything
    assert A_PASSWORD not in everything
    assert "bea@example.com" not in everything and "2026-01-10" not in everything


def test_viewer_sees_their_side_of_a_link(conn, users):
    a, b = users
    partner.redeem_invite(conn, b, partner.create_invite(conn, a).invite_code)
    assert _zip(conn, b)["partner_links.csv"].splitlines()[1].startswith(f"viewing,{A_NAME},accepted,")


# --- delete all my data -------------------------------------------------------

def test_delete_requires_the_matching_email(conn, users):
    a, _ = users
    with pytest.raises(ValueError, match="doesn't match"):
        db.delete_account(conn, a, "someone-else@example.com")
    assert auth.get_user(conn, a) is not None
    assert len(db.get_logs(conn, a)) == 25


def test_delete_removes_everything_and_spares_others(conn, users):
    a, b = users
    partner.redeem_invite(conn, b, partner.create_invite(conn, a).invite_code)
    partner.redeem_invite(conn, a, partner.create_invite(conn, b).invite_code)
    b_before = (db.get_logs(conn, b), db.get_cycles(conn, b))

    db.delete_account(conn, a, "  ZEPHYRINE@example.com ")  # case/space-insensitive

    assert auth.get_user(conn, a) is None
    assert auth.login(conn, A_EMAIL, A_PASSWORD) is None
    for table in ("daily_log", "daily_symptom", "cycle"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (a,)).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM partner_links WHERE user_id = ? OR partner_user_id = ?", (a, a)
    ).fetchone()[0] == 0
    assert (db.get_logs(conn, b), db.get_cycles(conn, b)) == b_before


def _secrets_of_a(conn, a) -> list[bytes]:
    stored_hash = conn.execute("SELECT password_hash FROM users WHERE id = ?", (a,)).fetchone()[0]
    return [A_NAME.encode(), A_EMAIL.encode(), stored_hash.encode()]


def test_deleted_data_is_gone_from_the_raw_file(db_path, conn, users):
    a, _ = users
    secrets = _secrets_of_a(conn, a)
    raw = db_path.read_bytes()
    assert all(s in raw for s in secrets)  # sanity: the grep can see them first

    db.delete_account(conn, a, A_EMAIL)
    conn.close()

    raw = db_path.read_bytes()
    for s in secrets:
        assert s not in raw, f"{s!r} still in the database file after deletion"
    leftovers = [p.name for p in db_path.parent.iterdir() if p.name != db_path.name]
    assert leftovers == []  # no journal/WAL file holding old pages


def test_grep_would_catch_leftovers_without_secure_delete(db_path, users):
    # Control: proves the grep above is meaningful. With secure_delete off,
    # SQLite leaves the deleted rows' bytes in free pages, and the grep
    # finds them.
    a, _ = users
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA secure_delete = OFF")
    secrets = _secrets_of_a(conn, a)
    db.delete_account(conn, a, A_EMAIL)
    conn.close()
    raw = db_path.read_bytes()
    assert any(s in raw for s in secrets)


def test_pdf_says_when_the_predicted_period_is_overdue(conn, users):
    # A's open cycle started May 9; with cycles 28/30/29/41 the next is
    # expected in June. By August it's overdue and the PDF must say so
    # rather than show a stale range as if it were still ahead.
    a, _ = users
    text = _pdf_text(export.doctor_pdf(export.build_doctor_report(conn, a, today=date(2026, 8, 1))))
    assert "none logged as of 01 Aug 2026" in text
    assert "was expected between" in text
