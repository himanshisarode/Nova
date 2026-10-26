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
