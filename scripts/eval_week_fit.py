"""Week Fit evaluation (spec.md "LLM layer (Level 2)", Evaluation).

NOT part of pytest: it calls the real provider and costs a little money.

    python scripts/eval_week_fit.py run      # needs ANTHROPIC_API_KEY
    # ...open eval/week_fit_marks.csv, put 1 (respects the note) or 0
    #    (doesn't) in the "sensible" column for every day with a note...
    python scripts/eval_week_fit.py score

`run` sends each of the ~15 hand-built weeks in eval/week_fit_samples.json
through the real week_fit code path (same payload, same validation) and
reports (a) how often the raw reply passed validation with no fallback at
all, and writes eval/week_fit_marks.csv for the owner's marks. `score`
reads the marks and reports (b) the sensible-fit rate. Both numbers go
in README.md as informational, with the small-sample caveat.

Uses a throwaway in-memory database and lifts the daily cap for this run
only (the cap protects the live app, not a deliberate evaluation).
"""
import csv
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import auth  # noqa: E402
import db  # noqa: E402
import llm  # noqa: E402
import week_fit  # noqa: E402

SAMPLES = ROOT / "eval" / "week_fit_samples.json"
MARKS = ROOT / "eval" / "week_fit_marks.csv"


def load_weeks(path: Path = SAMPLES) -> list[tuple[int, list[week_fit.DayPlan], list[str]]]:
    weeks = []
    for w in json.loads(path.read_text(encoding="utf-8"))["weeks"]:
        plans = [
            week_fit.DayPlan(d["day"], date(2000, 1, 1), frozenset(d["buckets"]),
                             tuple((s, t) for s, t in d["offered"]))
            for d in w["days"]
        ]
        weeks.append((w["id"], plans, [d["note"] for d in w["days"]]))
    return weeks


def run(marks_path: Path = MARKS) -> dict:
    if not llm.has_key():
        print(f"Set {llm.API_KEY_ENV} first — this script calls the real provider.")
        return {}
    weeks = load_weeks()
    conn = db.connect(":memory:")
    user = auth.signup(conn, "eval@example.com", "password-eval-1", "Eval").id
    db.update_settings(conn, user, week_fit_opt_in=True)
    llm.DAILY_CAPS["week_fit"] = len(weeks)  # this process only
    clean = failed = 0
    rows = []
    for week_id, plans, notes in weeks:
        result = week_fit.generate(conn, user, plans, notes, gate_open=True)
        if result.source == "llm" and result.dropped_days == 0:
            clean += 1
        if result.source == "template":
            failed += 1
        for day in result.days:
            rows.append({"week": week_id, "day": day.day_name, "note": day.note,
                         "strategies": "; ".join(day.strategies), "sentence": day.sentence,
                         "source": day.source, "sensible": ""})
    with marks_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"weeks": len(weeks), "passed_validation_fully": clean, "whole_week_template": failed,
               "days_from_template": sum(r["source"] == "template" for r in rows), "days": len(rows)}
    print(json.dumps(summary, indent=2))
    print(f"(a) raw reply passed validation with no fallback: {clean}/{len(weeks)} weeks")
    print(f"Now mark {marks_path} and run: python scripts/eval_week_fit.py score")
    return summary


def score(marks_path: Path = MARKS) -> float | None:
    with marks_path.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["note"].strip()]
    marked = [r for r in rows if r["sensible"].strip() in ("0", "1")]
    if not marked:
        print("No marks yet: put 1 or 0 in the 'sensible' column for each day with a note.")
        return None
    rate = sum(r["sensible"].strip() == "1" for r in marked) / len(marked)
    print(f"(b) sensible-fit rate: {rate:.0%} of {len(marked)} marked days "
          f"({len(rows) - len(marked)} days with a note still unmarked). Small sample: informational only.")
    return rate


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else ""
    if command == "run":
        run()
    elif command == "score":
        score()
    else:
        print(__doc__)
