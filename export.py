"""Doctor export (Feature 6) and export-my-data (Feature 7).

The doctor export is a cycle-level summary, not a diary: no email, mood,
lifestyle tags, remedy log, SHAP explanations, or partner details. Its
irregularity column says what happened ("12 days longer than your usual
29"), never why — the factors behind a "why" are deliberately left out of
this export, and the reason text must not bring them back in.

Export-my-data is the opposite: everything the user owns, as CSVs in a
ZIP, except secrets (password hash, invite codes).
"""
import calendar
import csv
import io
import json
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from statistics import mean, median
from xml.sax.saxutils import escape

import auth
import db
import irregularity
import predict
import theme

RANGE_CHOICES: dict[str, int | None] = {
    "Last 3 months": 3, "Last 6 months": 6, "Last 12 months": 12, "All time": None,
}
DEFAULT_RANGE = "Last 12 months"

CSV_COLUMNS = (
    "cycle_start", "cycle_end", "length_days", "period_days", "heaviest_flow",
    "irregular", "what_happened", "symptoms",
)


@dataclass(frozen=True)
class CycleRow:
    start: date
    end: date
    length: int
    period_days: int
    heaviest_flow: str | None
    irregular: bool
    reason: str  # what happened, never why; empty if regular
    symptoms: dict[str, int]  # symptom -> days logged in this cycle


@dataclass(frozen=True)
class DoctorReport:
    display_name: str
    range_start: date | None  # None = all time
    range_end: date
    rows: list[CycleRow]
    prediction: predict.HonestPrediction | predict.NotEnoughData

    @property
    def lengths(self) -> list[int]:
        return [r.length for r in self.rows]

    def symptom_share(self) -> dict[str, float]:
        """Share of the report's cycles with each symptom logged at least once."""
        if not self.rows:
            return {}
        return {
            s: sum(1 for r in self.rows if r.symptoms.get(s)) / len(self.rows)
            for s in db.SYMPTOMS
            if any(r.symptoms.get(s) for r in self.rows)
        }


def months_before(day: date, months: int) -> date:
    """Same day-of-month `months` earlier, clamped to the month's last day."""
    year, month0 = divmod(day.year * 12 + day.month - 1 - months, 12)
    month = month0 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def _cycle_rows(cycles: list[db.Cycle], logs: list[db.LogEntry]) -> list[CycleRow]:
    by_day = {e.date: e for e in logs}
    rows = []
    for cycle, assessment in zip(cycles, irregularity.assess_cycles(cycles)):
        days = [by_day.get(cycle.start + timedelta(days=k)) for k in range(cycle.length)]
        logged = [d for d in days if d is not None]
        flows = [d.flow for d in logged if d.flow in db.BLEEDING_FLOWS]
        symptoms: dict[str, int] = {}
        for d in logged:
            for s in d.symptoms:
                symptoms[s] = symptoms.get(s, 0) + 1
        rows.append(CycleRow(
            start=cycle.start,
            end=cycle.end,
            length=cycle.length,
            period_days=len(flows),
            heaviest_flow=max(flows, key=db.FLOW_LEVELS.index) if flows else None,
            irregular=assessment.irregular,
            reason=assessment.reason,
            symptoms=dict(sorted(symptoms.items())),
        ))
    return rows


def build_doctor_report(
    conn: sqlite3.Connection, user_id: int, months: int | None = 12, today: date | None = None
) -> DoctorReport:
    """Cycles that started in the chosen range, plus the current prediction.

    Irregularity is judged against the user's whole history (so a cycle
    early in the range still has a "usual" to compare with), then filtered.
    """
    today = today or date.today()
    user = auth.get_user(conn, user_id)
    cycles = db.get_cycles(conn, user_id)
    rows = _cycle_rows(cycles, db.get_logs(conn, user_id))
    range_start = months_before(today, months) if months else None
    rows = [r for r in rows if (range_start is None or r.start >= range_start) and r.start <= today]
    starts = db.get_period_starts(conn, user_id)
    prediction = (
        predict.honest_prediction([c.length for c in cycles], starts[-1])
        if starts else predict.NotEnoughData(have=0)
    )
    return DoctorReport(user.display_name, range_start, today, rows, prediction)


# --- CSV ----------------------------------------------------------------------

def doctor_csv(report: DoctorReport) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for r in report.rows:
        writer.writerow([
            r.start.isoformat(), r.end.isoformat(), r.length, r.period_days,
            r.heaviest_flow or "", "yes" if r.irregular else "no", r.reason,
            "; ".join(f"{s}:{n}" for s, n in r.symptoms.items()),
        ])
    return out.getvalue()


# --- PDF ----------------------------------------------------------------------

def _fmt(d: date) -> str:
    return d.strftime("%d %b %Y")


def doctor_pdf(report: DoctorReport) -> bytes:
    # reportlab is only needed here; keep it out of every other import path.
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    blush, lavender, charcoal = colors.HexColor("#F6C6CE"), colors.HexColor("#D9C9E8"), colors.HexColor("#3B3436")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], textColor=charcoal, fontSize=9.5, leading=13)
    small = ParagraphStyle("small", parent=body, fontSize=7.5, leading=10, textColor=colors.HexColor("#6B6064"))
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=charcoal, fontSize=18, alignment=0)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=charcoal, fontSize=12, spaceBefore=8)

    period = (
        f"{_fmt(report.range_start)} – {_fmt(report.range_end)}" if report.range_start
        else f"All logged cycles up to {_fmt(report.range_end)}"
    )
    story = [
        Paragraph("Cycle summary", h1),
        Paragraph(
            f"<b>{escape(report.display_name)}</b> · {period} · generated {_fmt(report.range_end)}", body
        ),
        Spacer(1, 4 * mm),
        Paragraph("Summary", h2),
    ]

    lengths = report.lengths
    if lengths:
        p = report.prediction
        if not isinstance(p, predict.HonestPrediction):
            next_period = "not enough completed cycles to predict"
        elif predict.is_late(p, report.range_end):
            next_period = (
                f"was expected between {_fmt(p.earliest)} and {_fmt(p.latest)} "
                f"(90% prediction interval); none logged as of {_fmt(report.range_end)}"
            )
        else:
            next_period = f"between {_fmt(p.earliest)} and {_fmt(p.latest)} (90% prediction interval)"
        summary = [
            ("Completed cycles", str(len(lengths))),
            ("Cycle length, average / median", f"{mean(lengths):.1f} / {median(lengths):g} days"),
            ("Shortest / longest", f"{min(lengths)} / {max(lengths)} days"),
            ("Typical period length", f"{median(r.period_days for r in report.rows):g} days"),
            ("Irregular cycles", f"{sum(r.irregular for r in report.rows)} of {len(lengths)}"),
            ("Next period", next_period),
        ]
        story.append(Table(
            [[Paragraph(k, body), Paragraph(v, body)] for k, v in summary],
            colWidths=[60 * mm, 110 * mm], hAlign="LEFT",
            style=TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]),
        ))

        story.append(Paragraph("Cycle lengths", h2))
        drawing = Drawing(170 * mm, 50 * mm)
        chart = VerticalBarChart()
        chart.x, chart.y, chart.width, chart.height = 12 * mm, 8 * mm, 150 * mm, 38 * mm
        chart.data = [lengths]
        chart.categoryAxis.categoryNames = [r.start.strftime("%d %b %y") for r in report.rows]
        chart.categoryAxis.labels.fontSize = 6
        chart.categoryAxis.labels.angle = 45 if len(lengths) > 8 else 0
        chart.categoryAxis.labels.boxAnchor = "ne" if len(lengths) > 8 else "n"
        chart.valueAxis.valueMin = 0
        chart.valueAxis.labels.fontSize = 7
        chart.bars[0].fillColor = blush
        chart.bars[0].strokeColor = None
        for i, r in enumerate(report.rows):
            if r.irregular:
                chart.bars[(0, i)].fillColor = lavender
        drawing.add(chart)
        story += [drawing, Paragraph("Lavender bars are cycles flagged as irregular.", small)]

        story.append(Paragraph("Cycles", h2))
        header = ["Start", "Length", "Period days", "Heaviest flow", "Irregular?"]
        table = [header] + [
            [_fmt(r.start), f"{r.length} d", str(r.period_days), r.heaviest_flow or "—",
             Paragraph(escape(f"Yes — {r.reason}") if r.irregular else "No", small)]
            for r in report.rows
        ]
        story.append(Table(
            table, repeatRows=1,
            colWidths=[26 * mm, 16 * mm, 20 * mm, 24 * mm, 84 * mm],
            style=TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), blush),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FFF8F3")]),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#E8C5CC")),
            ]),
        ))

        shares = report.symptom_share()
        story.append(Paragraph("Symptoms", h2))
        if shares:
            story.append(Paragraph(
                "Share of these cycles where each symptom was logged at least once.", small
            ))
            story.append(Table(
                [[s.replace("_", " "), f"{share:.0%}"] for s, share in
                 sorted(shares.items(), key=lambda kv: -kv[1])],
                colWidths=[60 * mm, 20 * mm], hAlign="LEFT",
                style=TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8.5)]),
            ))
        else:
            story.append(Paragraph("No symptoms were logged in these cycles.", body))
    else:
        story.append(Paragraph("No completed cycles in this date range.", body))

    disclaimer = Paragraph(escape(theme.MEDICAL_DISCLAIMER), small)

    def footer(canvas, doc):
        width = A4[0] - 30 * mm
        _, height = disclaimer.wrap(width, 30 * mm)
        disclaimer.drawOn(canvas, 15 * mm, 8 * mm)
        canvas.setStrokeColor(lavender)
        canvas.line(15 * mm, 10 * mm + height, A4[0] - 15 * mm, 10 * mm + height)

    out = io.BytesIO()
    SimpleDocTemplate(
        out, pagesize=A4, title="Cycle summary", author="Nova",
        leftMargin=15 * mm, rightMargin=15 * mm, topMargin=15 * mm, bottomMargin=32 * mm,
    ).build(story, onFirstPage=footer, onLaterPages=footer)
    return out.getvalue()


# --- export my data -------------------------------------------------------------

def _csv(header: list[str], rows: list[list]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def export_my_data(conn: sqlite3.Connection, user_id: int) -> bytes:
    """Everything the user owns, as a ZIP of CSVs + account.json.

    Never includes the password hash or invite codes.
    """
    user = auth.get_user(conn, user_id)
    logs = db.get_logs(conn, user_id)
    files = {
        "account.json": json.dumps(
            {"email": user.email, "display_name": user.display_name, "created_at": user.created_at},
            indent=2,
        ),
        "daily_log.csv": _csv(
            ["date", "flow", "mood", "symptoms", *db.LIFESTYLE_TAGS],
            [
                [e.date.isoformat(), e.flow or "", "" if e.mood is None else e.mood,
                 "; ".join(sorted(e.symptoms)), *(int(getattr(e, t)) for t in db.LIFESTYLE_TAGS)]
                for e in logs
            ],
        ),
        "cycles.csv": _csv(
            ["start", "end", "length_days"],
            [[c.start.isoformat(), c.end.isoformat(), c.length] for c in db.get_cycles(conn, user_id)],
        ),
        "remedy_log.csv": _csv(
            ["date", "symptom", "remedy", "relief_rating"],
            [[r.date.isoformat(), r.symptom, r.remedy, r.relief_rating]
             for r in db.get_remedies(conn, user_id)],
        ),
        "partner_links.csv": _csv(
            ["role", "other_person", "status", "created_at", "accepted_at", "revoked_at"],
            [
                [role, other or "", status, created, accepted or "", revoked or ""]
                for role, other, status, created, accepted, revoked in conn.execute(
                    "SELECT CASE WHEN l.user_id = ? THEN 'sharing_with' ELSE 'viewing' END,"
                    " u.display_name, l.status, l.created_at, l.accepted_at, l.revoked_at"
                    " FROM partner_links l LEFT JOIN users u"
                    "   ON u.id = CASE WHEN l.user_id = ? THEN l.partner_user_id ELSE l.user_id END"
                    " WHERE l.user_id = ? OR l.partner_user_id = ?"
                    " ORDER BY l.created_at",
                    (user_id, user_id, user_id, user_id),
                )
            ],
        ),
    }
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            zf.writestr(name, content)
    return out.getvalue()
