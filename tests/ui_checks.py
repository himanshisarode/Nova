"""AppTest helpers for checking the medical disclaimer is really on screen.

Shared by every page test (SPEC.md acceptance: the disclaimer renders in
the same card as each prediction/flag, and in every page's footer).
"""
from html import unescape

from streamlit.testing.v1 import AppTest

from theme import MEDICAL_DISCLAIMER


def _walk(node):
    children = getattr(node, "children", None)
    if children is None:
        return
    for child in children.values() if isinstance(children, dict) else children:
        yield child
        yield from _walk(child)


def _html_bodies(node) -> list[str]:
    return [unescape(el.proto.body) for el in _walk(node) if getattr(el, "type", None) == "html"]


def card(at: AppTest, name: str):
    """The card created with theme.card(name, ...), found by its key suffix."""
    matches = [
        el for el in _walk(at.main)
        if getattr(el, "type", None) == "flex_container"
        and str(getattr(el.proto, "id", "")).endswith(f"-{name}")
        and "nova-card" in str(el.proto.id)
    ]
    assert len(matches) == 1, f"expected exactly one card named {name!r}, found {len(matches)}"
    return matches[0]


def card_has_disclaimer(at: AppTest, name: str) -> bool:
    return any(MEDICAL_DISCLAIMER in body for body in _html_bodies(card(at, name)))


def footer_has_disclaimer(at: AppTest) -> bool:
    """True if the page's last element is the footer and it carries the disclaimer."""
    last = list(at.main.children.values())[-1]
    return (
        getattr(last, "type", None) == "html"
        and 'class="nova-footer"' in last.proto.body
        and MEDICAL_DISCLAIMER in unescape(last.proto.body)
    )
