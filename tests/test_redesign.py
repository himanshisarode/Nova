"""Visual redesign: presentation-only checks (icons, art, wellness tiles,
season strip). The logic underneath is tested elsewhere and unchanged."""
import ast
import re
from pathlib import Path

from streamlit.material_icon_names import ALL_MATERIAL_ICONS

ROOT = Path(__file__).parent.parent
UI_FILES = ("app.py", "theme.py", "seasons.py", "art.py")


def _page_icons() -> dict:
    tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", "") == "PAGE_ICONS":
            return ast.literal_eval(node.value)
    raise AssertionError("PAGE_ICONS not found")


def test_every_page_has_a_valid_material_icon():
    import ast as _ast
    pages = None
    for node in _ast.parse((ROOT / "app.py").read_text(encoding="utf-8")).body:
        if isinstance(node, _ast.Assign) and getattr(node.targets[0], "id", "") == "PAGES":
            pages = _ast.literal_eval(node.value)
    icons = _page_icons()
    assert set(icons) == set(pages)
    assert all(name in ALL_MATERIAL_ICONS for name in icons.values()), icons


def test_every_icon_name_used_in_the_ui_is_valid():
    used = set()
    for name in UI_FILES:
        path = ROOT / name
        if path.exists():
            text = path.read_text(encoding="utf-8")
            used |= set(re.findall(r":material/([a-z0-9_]+):", text))
            used |= set(re.findall(r'icon="([a-z0-9_]+)"', text))
    assert used, "no icons found"
    assert not used - ALL_MATERIAL_ICONS, used - ALL_MATERIAL_ICONS


def test_corner_art_is_inline_still_and_unclickable():
    import art

    css = art.corner_css()
    assert "data:image/svg+xml" in css
    assert "http" not in css.replace("http://www.w3.org/2000/svg", "")  # nothing hotlinked
    assert "animation" not in css
    # Background images can't receive pointer events or cover text: cards
    # and the footer paint over them.
    assert "background-image" in css and "::before" not in css and "::after" not in css
    assert 0 < art.OPACITY <= 0.5


def test_footer_keeps_an_opaque_backing_over_the_art():
    css = (ROOT / "assets" / "nova.css").read_text(encoding="utf-8")
    footer = css.split(".nova-footer {", 1)[1].split("}", 1)[0]
    assert "background" in footer and "z-index" in footer


# --- Today's wellness tiles -----------------------------------------------------------

def _tiles_html(at) -> str:
    from html import unescape
    bodies = [unescape(h.proto.body) for h in at.get("html") if 'class="nova-tiles"' in h.proto.body]
    assert len(bodies) == 1
    return bodies[0]


def test_new_user_gets_warm_empty_tiles_and_no_invented_numbers(tmp_path, monkeypatch):
    import auth
    import db
    from tests.test_app import app, goto

    monkeypatch.setenv("NOVA_DB_PATH", str(tmp_path / "nova.db"))
    conn = db.connect(tmp_path / "nova.db")
    user = auth.signup(conn, "new@example.com", "password-new-1", "New")
    html = _tiles_html(goto(app(user), "Today"))
    assert html.count("Not logged yet") == 3
    assert "Coming later" in html
    assert not re.search(r"\d", html.replace("nova-tile", ""))  # no numbers at all
    conn.close()


def test_tiles_show_exactly_todays_logged_values(tmp_path, monkeypatch):
    from datetime import date

    import auth
    import db
    from tests.test_app import app, goto

    monkeypatch.setenv("NOVA_DB_PATH", str(tmp_path / "nova.db"))
    conn = db.connect(tmp_path / "nova.db")
    user = auth.signup(conn, "a@example.com", "password-a-1", "A")
    db.save_log(conn, user.id, db.LogEntry(date.today(), mood=2, energy=4, symptoms=frozenset({"cramps"})))
    html = _tiles_html(goto(app(user), "Today"))
    assert "4 of 5" in html and "2 of 5" in html and "cramps" in html
    conn.close()


def test_strategy_tile_matches_plan_my_week_for_today(tmp_path, monkeypatch):
    from datetime import date

    import auth
    import db
    import phases
    import week_fit
    import whatworks
    from tests.test_app import app, goto
    from tests.test_level2_app import seed_level2

    monkeypatch.setenv("NOVA_DB_PATH", str(tmp_path / "nova.db"))
    conn = db.connect(tmp_path / "nova.db")
    user = seed_level2(conn)
    html = _tiles_html(goto(app(user), "Today"))
    logs = db.get_logs(conn, user.id)
    starts = db.get_period_starts(conn, user.id)
    bleeding = [e.date for e in logs if e.flow in db.BLEEDING_FLOWS]
    lengths = [c.length for c in db.get_cycles(conn, user.id)]
    period_days = phases.typical_period_days(starts, bleeding)
    current = phases.current_cycle(starts, bleeding, lengths, date.today(), None, period_days)
    findings = whatworks.goes_well(whatworks.analyse(whatworks.rated_days(starts, logs)))
    offered = week_fit.plan_days(date.today(), current, period_days, findings)[0].offered
    for s, _ in offered[:3]:
        assert whatworks.strategy_label(s) in html.lower()
    if not offered:
        assert "Nothing stands out" in html or "Not sure yet" in html
    conn.close()


# --- seasons strip ---------------------------------------------------------------------

def _cycle(**kw):
    from datetime import date, timedelta

    import phases

    start = date(2026, 10, 1)
    d = lambda n: start + timedelta(days=n)  # noqa: E731
    base = dict(start=start, day=9, period_end=d(4), enough_data=True, next_earliest=d(27),
                next_latest=d(30), ovulation_from=d(11), ovulation_to=d(16), luteal_from=d(17),
                phase_today="follicular")
    base.update(kw)
    return phases.CurrentCycle(**base)


def test_strip_segments_are_sized_from_the_estimated_windows():
    import seasons

    segs = seasons.strip_segments(_cycle())
    assert [(s.season, s.days) for s in segs] == [
        ("Winter", 5), ("Spring", 6), ("Summer", 6), ("Autumn", 10), ("", 4)]
    assert sum(s.days for s in segs) == 31  # start .. latest possible next start


def test_strip_is_labelled_as_estimates_and_marks_today():
    import seasons

    html = seasons.strip_html(_cycle())
    assert "~5 days" in html and "luteal, or your next period" in html
    assert "left:27.4%" in html  # (day 9 - 0.5) / 31
    assert "estimated" in seasons.STRIP_CAPTION and "not dates" in seasons.STRIP_CAPTION


def test_strip_explains_a_spring_hidden_by_a_wide_window():
    from datetime import date

    import seasons

    html = seasons.strip_html(_cycle(ovulation_from=date(2026, 10, 6)))
    assert "too uncertain to draw apart" in html


def test_my_phases_shows_the_strip_but_not_with_hormonal_contraception(tmp_path, monkeypatch):
    import db
    from tests.test_app import app, goto
    from tests.test_level2_app import seed_level2
    from tests.ui_checks import card_has_disclaimer

    monkeypatch.setenv("NOVA_DB_PATH", str(tmp_path / "nova.db"))
    conn = db.connect(tmp_path / "nova.db")
    user = seed_level2(conn)
    at = goto(app(user), "My phases")
    assert any('class="nova-strip"' in h.proto.body for h in at.get("html"))
    assert card_has_disclaimer(at, "phase-tracker")
    db.update_settings(conn, user.id, hormonal_contraception=True)
    at = goto(app(user), "My phases")
    assert not any('class="nova-strip"' in h.proto.body for h in at.get("html"))
    conn.close()
