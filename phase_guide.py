"""Phase Guide — LLM call 1 (spec.md Feature 22, "LLM layer (Level 2)").

"What tends to go well for me in each phase?", written up from the local
findings (whatworks.goes_well). Local code decides WHAT is true; the
model only phrases it, plus one sentence about the typical cycle-length
range (two numbers). Payload: phase labels, strategy labels, tiers, two
numbers — no dates, no free text, no identity, no logs (spec.md
Constraints). Output is validated; any violation → the template.

Generated at most once per completed cycle (stored in phase_guide, keyed
by the newest completed cycle's start). Off until the user opts in, only
after the gate, never for hormonal contraception — enforced here, not
just in the UI.
"""
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

import db
import llm
import phases
import whatworks
import wording

CALL_TYPE = "phase_guide"
# Labels sent to the model and shown on the page. Deliberately free of
# "ovulation"/"fertile" wording (the follicular bucket includes the
# ovulation window; the page explains that).
PHASE_NAMES = {"period": "Period days", "follicular": "Follicular phase", "luteal": "Luteal phase"}
MAX_PHASE_CHARS = 400
MAX_CYCLE_CHARS = 200

SYSTEM = """You write a short, warm, plain-English summary for one person of what tends to go well for her in each phase of her menstrual cycle, using only findings from her own logs that are given to you as JSON.

Rules:
- For each phase, write 1-2 sentences mentioning only the strategies listed for that phase, with their evidence level in plain words. If a phase has none, say that nothing stands out in her data for that phase yet.
- Use associative wording: "tends to", "in your data", "days with ... tended to go well". Never say a strategy causes anything, never give instructions ("should", "must"), never mention hormones, health, symptoms, food or medical topics, and never claim energy, creativity or intuition changes by phase.
- Never mention any activity that is not listed for that phase.
- cycle_sentence: one sentence saying her cycles have usually run between the two given numbers of days. Use only those two numbers.
- Reply only with JSON matching the schema."""

SCHEMA = {
    "type": "object",
    "properties": {
        "phases": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phase": {"type": "string", "enum": list(PHASE_NAMES.values())},
                    "text": {"type": "string"},
                },
                "required": ["phase", "text"],
                "additionalProperties": False,
            },
        },
        "cycle_sentence": {"type": "string"},
    },
    "required": ["phases", "cycle_sentence"],
    "additionalProperties": False,
}

Findings = dict[str, list[tuple[str, str]]]  # whatworks.goes_well()


@dataclass(frozen=True)
class Guide:
    sections: list[tuple[str, str]]  # (phase name, text), in bucket order
    cycle_sentence: str
    source: str  # "llm" or "template"
    notice: str = ""  # why the template is showing, if it is
    created_at: str = field(default="", compare=False)


def payload(findings: Findings, cycle_range: tuple[int, int]) -> dict:
    """Everything the model sees: labels, tiers, two whole numbers."""
    return {
        "phases": [
            {
                "phase": PHASE_NAMES[b],
                "tends_to_go_well": [
                    {"strategy": whatworks.strategy_label(s), "evidence": tier} for s, tier in findings[b]
                ],
            }
            for b in phases.BUCKETS
        ],
        "typical_cycle_length_days": {"shortest": int(cycle_range[0]), "longest": int(cycle_range[1])},
    }


def template(findings: Findings, cycle_range: tuple[int, int], notice: str = "") -> Guide:
    sections = []
    for b in phases.BUCKETS:
        if findings[b]:
            items = ", ".join(f"{whatworks.strategy_label(s)} ({tier})" for s, tier in findings[b])
            sections.append((PHASE_NAMES[b], f"In your data, these tend to go well during this phase: {items}."))
        else:
            sections.append((PHASE_NAMES[b], "Nothing stands out clearly in your data for this phase yet."))
    lo, hi = cycle_range
    sentence = f"Your recent cycles have run between {lo} and {hi} days."
    return Guide(sections, sentence, "template", notice)


def validate(raw: dict, findings: Findings, cycle_range: tuple[int, int]) -> Guide | None:
    """The model's guide if it passes every check, else None (→ template)."""
    try:
        items = {item["phase"]: item["text"] for item in raw["phases"]}
        sentence = raw["cycle_sentence"]
    except (KeyError, TypeError):
        return None
    if len(raw["phases"]) != len(phases.BUCKETS) or set(items) != set(PHASE_NAMES.values()):
        return None
    if not isinstance(sentence, str) or not all(isinstance(t, str) for t in items.values()):
        return None
    sections = []
    for b in phases.BUCKETS:
        text = items[PHASE_NAMES[b]].strip()
        allowed = {s for s, _ in findings[b]}
        if not text or len(text) > MAX_PHASE_CHARS or wording.banned_words(text):
            return None
        if wording.strategies_mentioned(text) - allowed:
            return None
        if allowed and "tend" not in text.lower():
            return None
        sections.append((PHASE_NAMES[b], text))
    if (len(sentence) > MAX_CYCLE_CHARS or wording.banned_words(sentence)
            or not wording.numbers_in(sentence) <= set(cycle_range)
            or wording.strategies_mentioned(sentence)):
        return None
    return Guide(sections, sentence.strip(), "llm")


# --- storage (once per completed cycle) -------------------------------------------

def stored(conn: sqlite3.Connection, user_id: int, cycle_start: date) -> Guide | None:
    row = conn.execute(
        "SELECT guide_json, created_at FROM phase_guide WHERE user_id = ? AND cycle_start = ?",
        (user_id, cycle_start.isoformat()),
    ).fetchone()
    if row is None:
        return None
    data = json.loads(row[0])
    return Guide([tuple(s) for s in data["sections"]], data["cycle_sentence"], "llm", created_at=row[1])


def _store(conn: sqlite3.Connection, user_id: int, cycle_start: date, guide: Guide) -> None:
    with conn:
        conn.execute(
            "INSERT INTO phase_guide (user_id, cycle_start, guide_json, created_at) VALUES (?, ?, ?, ?)",
            (user_id, cycle_start.isoformat(),
             json.dumps({"sections": guide.sections, "cycle_sentence": guide.cycle_sentence}),
             datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def allowed(settings: db.Settings, gate_open: bool, session_opt_in: bool = False) -> bool:
    """Opted in (the demo opts in per tab), past the gate, not on hormonal
    contraception."""
    opted_in = settings.phase_guide_opt_in or (settings.is_demo and session_opt_in)
    return opted_in and gate_open and not settings.hormonal_contraception


def generate(
    conn: sqlite3.Connection, user_id: int, findings: Findings, cycle_range: tuple[int, int],
    cycle_start: date, gate_open: bool, session_opt_in: bool = False,
) -> Guide:
    """Write the guide for this completed cycle, once. Always returns a
    guide: the model's if it worked and passed validation, else the
    template with a short notice saying why."""
    if (existing := stored(conn, user_id, cycle_start)) is not None:
        return existing
    if not allowed(db.get_settings(conn, user_id), gate_open, session_opt_in):
        return template(findings, cycle_range)
    try:
        raw = llm.request(conn, user_id, CALL_TYPE, SYSTEM, payload(findings, cycle_range), SCHEMA)
    except llm.LLMUnavailable as exc:
        return template(findings, cycle_range, notice=str(exc))
    guide = validate(raw, findings, cycle_range)
    if guide is None:
        return template(findings, cycle_range,
                        notice="The written version didn't pass Nova's checks, so here is the plain one.")
    _store(conn, user_id, cycle_start, guide)
    return guide
