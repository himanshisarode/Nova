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
