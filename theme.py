"""Shared look-and-feel helpers for every Nova page (SPEC.md "Design").

The base palette and font come from .streamlit/config.toml; this module
injects assets/nova.css on top and provides the card and empty-state
building blocks so pages don't hand-roll their own styling.
"""
from functools import lru_cache
from html import escape
from pathlib import Path

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

CSS_PATH = Path(__file__).parent / "assets" / "nova.css"
# plain = white card; blush/lavender = tinted; open = no box at all, so not
# every section is a white rectangle (used for page intros).
CARD_TONES = ("plain", "blush", "lavender", "open")

# SPEC.md "Medical disclaimer", word for word — tests/test_theme.py checks
# this against the spec so the two can't drift apart.
MEDICAL_DISCLAIMER = (
    "Nova's predictions, trend charts, and irregularity flags are based on "
    "statistical patterns in your own logged data. This is general "
    "information, not medical advice, and not a diagnosis. Cycle length, "
    "ovulation timing, and what counts as 'irregular' can be affected by "
    "many things this app doesn't know about. If something feels wrong, "
    "changes suddenly, or worries you, please talk to a doctor or "
    "gynecologist - don't rely on this app alone."
)


@lru_cache(maxsize=1)
def _css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def apply_theme() -> None:
    """Inject Nova's custom CSS. Call once near the top of every page."""
    st.html(f"<style>{_css()}</style>")


def card(name: str, tone: str = "plain") -> DeltaGenerator:
    """A soft-edged card container; use as `with card("stats"): ...`.

    `name` must be unique on the page (it becomes the container's key).
    """
    if tone not in CARD_TONES:
        raise ValueError(f"tone must be one of {CARD_TONES}, got {tone!r}")
    prefix = "nova-card" if tone == "plain" else f"nova-card-{tone}"
    return st.container(key=f"{prefix}-{name}")


def icon_html(name: str) -> str:
    """A Material Symbols (rounded) line icon — the same font Streamlit uses
    for `:material/...:` in the sidebar, so the two styles match."""
    return f'<span class="nova-icon" aria-hidden="true">{escape(name)}</span>'


def eyebrow(text: str, icon: str | None = None) -> None:
    """Small uppercase label above a card's title, with an optional icon."""
    mark = icon_html(icon) if icon else ""
    st.html(f'<div class="nova-eyebrow">{mark}{escape(text)}</div>')


def medical_disclaimer() -> None:
    """The standing disclaimer, inside the card of a prediction or flag.

    Required in the same card as every prediction, fertile-window
    estimate, and irregularity flag (SPEC.md). Never collapsed.
    """
    st.html(f'<div class="nova-disclaimer">🩺 {escape(MEDICAL_DISCLAIMER)}</div>')


def footer() -> None:
    """Page footer carrying the disclaimer. Call at the end of every page."""
    st.html(f'<footer class="nova-footer">{escape(MEDICAL_DISCLAIMER)}</footer>')


def empty_state(
    title: str,
    body: str,
    icon: str = "🌱",
    have: int | None = None,
    need: int | None = None,
) -> None:
    """A warm "not enough data yet" message, optionally with a progress bar.

    `have`/`need` show how close the user is to unlocking the feature
    (e.g. 2 of 3 cycles), so waiting reads as progress, not a refusal.
    """
    progress = ""
    if have is not None and need:
        pct = min(100, round(100 * have / need))
        progress = (
            f'<div class="nova-progress"><span style="width:{pct}%"></span></div>'
            f'<div class="nova-progress-label">{have} of {need} so far</div>'
        )
    st.html(
        '<div class="nova-empty">'
        f'<div class="nova-empty-icon">{escape(icon)}</div>'
        f'<div class="nova-empty-title">{escape(title)}</div>'
        f'<div class="nova-empty-body">{escape(body)}</div>'
        f"{progress}"
        "</div>"
    )
