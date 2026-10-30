"""Phase 16: the Week Fit evaluation script's plumbing, with the fake
provider (the script itself is for real calls and is never run by pytest
against the real API)."""
import csv
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load_script():
    spec = importlib.util.spec_from_file_location("eval_week_fit", ROOT / "scripts" / "eval_week_fit.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def first_offered(payload):
    return {"days": [
        {"day": d["day"], "strategies": [d["strategies"][0]["strategy"]] if d["strategies"] else [],
         "sentence": "That tends to go well for you around this." if d["strategies"]
                     else "Nothing in your data clearly fits this day."}
        for d in payload["days"]
    ]}


def test_samples_are_15_valid_weeks():
    weeks = load_script().load_weeks()
    assert len(weeks) == 15
    for _, plans, notes in weeks:
        assert len(plans) == 7 and len(notes) == 7
        assert len({p.day_name for p in plans}) == 7


def test_run_and_score_with_the_fake_provider(fake_llm, tmp_path, monkeypatch):
    import llm

    script = load_script()
    monkeypatch.setitem(llm.DAILY_CAPS, "week_fit", 5)  # restored after the test
    fake_llm.reply_fn = first_offered
    marks = tmp_path / "marks.csv"
    summary = script.run(marks)
    assert summary["weeks"] == 15 and summary["days"] == 105
    assert summary["whole_week_template"] == 0
    assert len(fake_llm.requests) == 15  # every week has at least one note
    rows = list(csv.DictReader(marks.open(encoding="utf-8")))
    for r in rows:
        r["sensible"] = "1" if r["note"] else ""
    with marks.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    assert script.score(marks) == 1.0


def test_run_refuses_without_a_key(monkeypatch, tmp_path):
    import llm

    monkeypatch.delenv(llm.API_KEY_ENV, raising=False)
    assert load_script().run(tmp_path / "m.csv") == {}
