"""Phase 0: the design system is wired up and the demo page renders."""
import tomllib
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).parent.parent


def test_config_uses_spec_palette():
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
    assert theme["backgroundColor"] == "#FFF8F3"
    assert theme["font"].startswith("Quicksand")


def test_font_is_self_hosted():
    theme = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["theme"]
    for face in theme["fontFaces"]:
        local = ROOT / face["url"].removeprefix("app/")
        assert local.is_file(), f"{face['url']} is not in static/"


def test_demo_page_renders_without_errors():
    at = AppTest.from_file(str(ROOT / "design_demo.py"), default_timeout=30).run()
    assert not at.exception
    assert at.metric[0].label == "Cycle day"


def test_card_rejects_unknown_tone():
    from theme import card

    with pytest.raises(ValueError):
        card("x", tone="neon")


def test_empty_state_escapes_text():
    def page():
        from theme import empty_state

        empty_state(title="<b>hi</b>", body="body", have=2, need=3)

    at = AppTest.from_function(page).run()
    assert not at.exception
    rendered = at.get("html")[0].proto.body
    assert "&lt;b&gt;hi&lt;/b&gt;" in rendered
    assert "2 of 3 so far" in rendered


# --- medical disclaimer -------------------------------------------------------

def _spec_disclaimer() -> str:
    """The blockquote under spec.md's "Medical disclaimer" heading, unwrapped."""
    spec = (ROOT / "spec.md").read_text(encoding="utf-8")
    section = spec.split("## Medical disclaimer", 1)[1].split("\n## ", 1)[0]
    quoted = [line[1:].strip() for line in section.splitlines() if line.startswith(">")]
    return " ".join(quoted)


def test_disclaimer_in_code_matches_spec_word_for_word():
    from theme import MEDICAL_DISCLAIMER

    assert MEDICAL_DISCLAIMER == _spec_disclaimer()


def test_demo_shows_disclaimer_with_its_prediction_and_in_footer():
    from tests.ui_checks import card_has_disclaimer, footer_has_disclaimer

    at = AppTest.from_file(str(ROOT / "design_demo.py"), default_timeout=30).run()
    assert card_has_disclaimer(at, "glance")  # the card showing "Next period"
    assert footer_has_disclaimer(at)


def test_disclaimer_check_is_not_trivially_true():
    # The helper must say "no" for a card that has no disclaimer, or the
    # check above proves nothing.
    from tests.ui_checks import card_has_disclaimer

    at = AppTest.from_file(str(ROOT / "design_demo.py"), default_timeout=30).run()
    assert not card_has_disclaimer(at, "welcome")


# --- seasons (phase-tinted background, design preview) ------------------------

def test_neutral_season_adds_no_css():
    import seasons

    assert seasons.season_css(seasons.NEUTRAL) == ""


def test_season_motifs_are_valid_data_uris():
    # An unescaped '#' (every colour) ends a data URI early and the motif
    # silently fails to load, so check each one parses as SVG.
    import re
    import xml.dom.minidom
    from urllib.parse import unquote

    import seasons

    for s in seasons.SEASONS.values():
        for uri in [svg for svg, _, _ in s.scene] + [s.drift]:
            body = re.fullmatch(r'url\("data:image/svg\+xml,(.*)"\)', uri).group(1)
            assert "#" not in body, s.name
            xml.dom.minidom.parseString(unquote(body))


@pytest.mark.parametrize("season", ["Neutral", "Winter", "Spring", "Summer", "Autumn"])
def test_demo_renders_every_season(season):
    at = AppTest.from_file(str(ROOT / "design_demo.py"), default_timeout=30)
    at.query_params["season"] = season
    at.run()
    assert not at.exception
    assert at.sidebar.radio[1].value == season
