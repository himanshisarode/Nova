"""Phase-tinted "seasons" for Nova's background (design preview only, so far).

Each cycle phase gets a season: a palette that overrides the CSS variables
in assets/nova.css, plus faint line-art motifs drawn behind the cards.
Cards stay cream in every season so text keeps its contrast; only the page
around them changes. The look is a mood, never a claim about how someone
feels, so captions name the phase and how Nova knows it, nothing more.

The page tint (season_css) is still preview-only: it animates, and the
redesign keeps the page still. What the app uses is the seasons strip at
the bottom of this file, a display-only picture on "My phases".
"""
import math
from dataclasses import dataclass
from datetime import date, timedelta
from html import escape
from urllib.parse import quote

import streamlit as st

NEUTRAL = "Neutral"


@dataclass(frozen=True)
class Season:
    name: str
    phase: str
    icon: str
    page: str  # page background base
    glow_a: str  # top-left glow
    glow_b: str  # top-right glow
    sidebar: str
    accent: str  # primary button / surfaces (was blush)
    accent_hover: str
    soft: str  # stat tiles, soft surfaces (was blush-soft)
    second: str  # secondary buttons (was lavender-soft)
    second_hover: str
    ink: str  # eyebrow labels, small accents
    swatches: tuple[str, ...]
    scene: tuple[tuple[str, str, str], ...]  # (svg, position, size)
    drift: str  # repeating svg tile that slowly moves
    drift_tile: int  # tile size in px
    drift_to: str  # background-position the drift animates to
    drift_seconds: int


def _svg(body: str, w: int, h: int) -> str:
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' "
        f"viewBox='0 0 {w} {h}' fill='none' stroke-linecap='round' "
        f"stroke-linejoin='round'>{body}</svg>"
    )
    return f'url("data:image/svg+xml,{quote(svg, safe=" =:/,\'")}")'  # '#' stays escaped: unescaped it ends the URI


# --- motifs ------------------------------------------------------------------
# Simple line art at low opacity: it should read as texture, not illustration.

def _ripples(color: str) -> str:
    rings = "".join(
        f"<ellipse cx='260' cy='130' rx='{r}' ry='{r * 0.32:.0f}' "
        f"stroke='{color}' stroke-width='2' opacity='{0.55 - i * 0.1:.2f}'/>"
        for i, r in enumerate((40, 90, 145, 205))
    )
    return _svg(rings, 520, 260)


def _mug(color: str) -> str:
    steam = "".join(
        f"<path d='M{x} 70 c-10 -14 10 -22 0 -36 c-8 -11 6 -18 0 -28' "
        f"stroke='{color}' stroke-width='3' opacity='0.6'/>"
        for x in (78, 100, 122)
    )
    cup = (
        f"<path d='M50 90 h100 v52 a38 38 0 0 1 -38 38 h-24 a38 38 0 0 1 -38 -38 z' "
        f"stroke='{color}' stroke-width='3.5'/>"
        f"<path d='M150 104 h12 a18 18 0 0 1 0 36 h-12' stroke='{color}' stroke-width='3.5'/>"
        f"<path d='M30 196 h140' stroke='{color}' stroke-width='3.5'/>"
    )
    return _svg(steam + cup, 200, 210)


def _rain(color: str) -> str:
    drops = "".join(
        f"<path d='M{x} {y} l-3 16' stroke='{color}' stroke-width='2.5' opacity='{o}'/>"
        for x, y, o in ((24, 18, 0.5), (92, 64, 0.35), (150, 10, 0.45), (58, 132, 0.4),
                        (126, 160, 0.5), (176, 104, 0.3))
    )
    return _svg(drops, 200, 200)


def _rising_sun(sun: str, line: str) -> str:
    rays = "".join(
        f"<path d='M160 150 m{dx * 78:.0f} {-dy * 78:.0f} l{dx * 26:.0f} {-dy * 26:.0f}' "
        f"stroke='{sun}' stroke-width='3.5'/>"
        for dx, dy in ((-1, 0), (-0.87, 0.5), (-0.5, 0.87), (0, 1),
                       (0.5, 0.87), (0.87, 0.5), (1, 0))
    )
    body = (
        f"<path d='M100 150 a60 60 0 0 1 120 0' stroke='{sun}' stroke-width='3.5'/>{rays}"
        f"<path d='M20 150 h280' stroke='{line}' stroke-width='3'/>"
        f"<path d='M70 168 h180' stroke='{line}' stroke-width='3' opacity='0.5'/>"
    )
    return _svg(body, 320, 180)


def _sprouts(color: str) -> str:
    def sprout(x: int, h: int) -> str:
        top = 170 - h
        return (
            f"<path d='M{x} 170 v-{h}' stroke='{color}' stroke-width='3.5'/>"
            f"<path d='M{x} {top + 14} c-22 -2 -34 -16 -34 -34 c20 0 34 14 34 34z' "
            f"stroke='{color}' stroke-width='3'/>"
            f"<path d='M{x} {top + 4} c20 -4 30 -20 28 -38 c-20 2 -30 18 -28 38z' "
            f"stroke='{color}' stroke-width='3'/>"
        )
    return _svg(sprout(60, 70) + sprout(150, 100) + sprout(240, 55), 300, 180)


def _petals(a: str, b: str) -> str:
    shapes = "".join(
        f"<ellipse cx='{x}' cy='{y}' rx='7' ry='4' transform='rotate({r} {x} {y})' "
        f"fill='{c}' opacity='0.45'/>"
        for x, y, r, c in ((30, 40, 30, a), (150, 20, -20, b), (100, 120, 60, a),
                           (200, 170, 10, b), (40, 190, -45, b), (180, 90, 80, a))
    )
    return _svg(shapes, 220, 220)


def _sunburst(color: str) -> str:
    rays = "".join(
        f"<path d='M{150 + 72 * math.cos(t):.1f} {150 + 72 * math.sin(t):.1f} "
        f"L{150 + (118 if i % 2 else 100) * math.cos(t):.1f} "
        f"{150 + (118 if i % 2 else 100) * math.sin(t):.1f}' "
        f"stroke='{color}' stroke-width='4'/>"
        for i, t in enumerate(k * math.pi / 8 for k in range(16))
    )
    body = (
        f"<circle cx='150' cy='150' r='56' stroke='{color}' stroke-width='4'/>"
        f"<circle cx='150' cy='150' r='36' fill='{color}' opacity='0.25'/>{rays}"
    )
    return _svg(body, 300, 300)


def _waves(a: str, b: str) -> str:
    def wave(y: int, color: str, o: float) -> str:
        return (
            f"<path d='M0 {y} q40 -26 80 0 t80 0 t80 0 t80 0 t80 0 t80 0' "
            f"stroke='{color}' stroke-width='3.5' opacity='{o}'/>"
        )
    return _svg(wave(40, a, 0.6) + wave(72, b, 0.5) + wave(104, a, 0.35), 480, 130)


def _sparkles(a: str, b: str) -> str:
    def star(x: int, y: int, s: int, c: str) -> str:
        return (
            f"<path d='M{x} {y - s} Q{x} {y} {x + s} {y} Q{x} {y} {x} {y + s} "
            f"Q{x} {y} {x - s} {y} Q{x} {y} {x} {y - s}z' fill='{c}' opacity='0.5'/>"
        )
    return _svg(
        star(40, 50, 7, a) + star(170, 30, 5, b) + star(120, 140, 8, a)
        + star(30, 180, 5, b) + star(200, 200, 6, a),
        240, 240,
    )


def _moon(moon: str, star: str) -> str:
    stars = "".join(
        f"<circle cx='{x}' cy='{y}' r='{r}' fill='{star}' opacity='0.6'/>"
        for x, y, r in ((40, 40, 3), (210, 30, 2.5), (230, 150, 3), (30, 170, 2), (120, 20, 2))
    )
    body = (
        f"<path d='M160 60 a64 64 0 1 0 40 108 a52 52 0 1 1 -40 -108z' "
        f"stroke='{moon}' stroke-width='3.5'/>{stars}"
    )
    return _svg(body, 250, 220)


def _leaf_path(x: int, y: int, r: int, color: str, o: float) -> str:
    return (
        f"<g transform='rotate({r} {x} {y})' opacity='{o}'>"
        f"<path d='M{x} {y - 18} c14 8 14 28 0 36 c-14 -8 -14 -28 0 -36z' "
        f"stroke='{color}' stroke-width='2.5'/>"
        f"<path d='M{x} {y - 14} v34' stroke='{color}' stroke-width='2'/></g>"
    )


def _falling_leaves(a: str, b: str) -> str:
    return _svg(
        _leaf_path(50, 50, 30, a, 0.55) + _leaf_path(190, 110, -40, b, 0.5)
        + _leaf_path(90, 200, 70, b, 0.45),
        260, 260,
    )


def _roots(color: str) -> str:
    body = (
        f"<path d='M150 10 v70' stroke='{color}' stroke-width='3.5'/>"
        f"<path d='M150 80 c-10 30 -50 40 -70 70 M150 80 c4 34 -10 60 -6 90 "
        f"M150 80 c14 26 50 34 66 66 M112 120 c-20 6 -34 2 -48 -6 M196 124 c14 10 30 10 46 4' "
        f"stroke='{color}' stroke-width='3'/>"
    )
    return _svg(body, 300, 190)


# --- the four seasons ---------------------------------------------------------

SEASONS: dict[str, Season] = {
    "Winter": Season(
        name="Winter", phase="period", icon="🌧️",
        page="#F3ECF3", glow_a="rgba(158, 120, 168, 0.40)", glow_b="rgba(120, 118, 178, 0.32)",
        sidebar="#EDE3F1",
        accent="#E3B3C2", accent_hover="#D9A0B2", soft="#F6EAF0",
        second="#ECE6F4", second_hover="#DCD2EC", ink="#7A4A72",
        swatches=("#6E4A6E", "#4E4A6E", "#9B8FA8", "#C98A9E"),
        scene=(
            (_mug("#8E6A92"), "right 4% bottom 5%", "170px"),
            (_ripples("#A887B0"), "right -120px top 16%", "460px"),
            (_ripples("#9E93C4"), "left 18% bottom -70px", "560px"),
        ),
        drift=_rain("#7C79A8"), drift_tile=200, drift_to="-60px 200px", drift_seconds=9,
    ),
    "Spring": Season(
        name="Spring", phase="follicular", icon="🌱",
        page="#F6F9F0", glow_a="rgba(168, 214, 176, 0.42)", glow_b="rgba(246, 222, 130, 0.38)",
        sidebar="#EEF5EA",
        accent="#BFDCB8", accent_hover="#ABD0A3", soft="#EEF6EA",
        second="#F7F1D6", second_hover="#EFE4B4", ink="#4F7F57",
        swatches=("#8DB596", "#A8DCC8", "#F2D46B", "#FBF9F2"),
        scene=(
            (_rising_sun("#E7C24E", "#9CC5A1"), "right -40px top 12%", "280px"),
            (_sprouts("#7FAE88"), "right 6% bottom 2%", "260px"),
        ),
        drift=_petals("#F2A7B8", "#F2D46B"), drift_tile=220, drift_to="220px -220px",
        drift_seconds=48,
    ),
    "Summer": Season(
        name="Summer", phase="ovulation", icon="☀️",
        page="#FFF4EA", glow_a="rgba(247, 160, 130, 0.38)", glow_b="rgba(245, 190, 90, 0.40)",
        sidebar="#FDEDE2",
        accent="#F7BFA4", accent_hover="#F2AA88", soft="#FDEEE4",
        second="#FCEBCB", second_hover="#F7DCA6", ink="#B0532F",
        swatches=("#F08A6E", "#F6B38A", "#E9A93A", "#C0643F"),
        scene=(
            (_sunburst("#EBA94A"), "right -110px top 4%", "340px"),
            (_waves("#EE9277", "#E9A93A"), "right 2% bottom 4%", "440px"),
        ),
        drift=_sparkles("#EE9277", "#E9A93A"), drift_tile=240, drift_to="-120px -240px",
        drift_seconds=40,
    ),
    "Autumn": Season(
        name="Autumn", phase="luteal", icon="🍂",
        page="#F8F0E4", glow_a="rgba(214, 140, 80, 0.32)", glow_b="rgba(150, 150, 90, 0.30)",
        sidebar="#F3E9DA",
        accent="#E9C29C", accent_hover="#E0AE80", soft="#F6EADB",
        second="#ECEBD6", second_hover="#DDDBB8", ink="#8A4F24",
        swatches=("#8B5E3C", "#D2783A", "#8A8B4A", "#F3E6CF"),
        scene=(
            (_moon("#A0784E", "#C99A5B"), "right -30px top 10%", "230px"),
            (_roots("#9C7A55"), "right 6% bottom 0", "260px"),
        ),
        drift=_falling_leaves("#C9773C", "#8A8B4A"), drift_tile=260, drift_to="-130px 260px",
        drift_seconds=36,
    ),
}


def season_css(name: str) -> str:
    """CSS overriding nova.css for one season; empty for the neutral look."""
    if name == NEUTRAL:
        return ""
    s = SEASONS[name]
    images = ", ".join(svg for svg, _, _ in s.scene)
    positions = ", ".join(pos for _, pos, _ in s.scene)
    sizes = ", ".join(size for _, _, size in s.scene)
    return f"""
:root {{
  --nova-blush: {s.accent};
  --nova-blush-hover: {s.accent_hover};
  --nova-blush-soft: {s.soft};
  --nova-lavender-soft: {s.second};
  --nova-lavender: {s.second_hover};
  --nova-ink: {s.ink};
  --nova-tint: {s.soft};
  --nova-tint-2: {s.second};
}}
.stApp {{
  background:
    radial-gradient(1100px 520px at 8% -10%, {s.glow_a}, transparent 60%),
    radial-gradient(900px 500px at 100% 0%, {s.glow_b}, transparent 60%),
    {s.page};
}}
.stApp::before, .stApp::after {{
  content: "";
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
}}
.stApp::before {{
  background-image: {images};
  background-position: {positions};
  background-size: {sizes};
  background-repeat: no-repeat;
  animation: nova-season-in 1.4s ease both;
}}
.stApp::after {{
  background-image: {s.drift};
  background-size: {s.drift_tile}px;
  opacity: 0.5;
  animation: nova-season-in 1.4s ease both, nova-drift {s.drift_seconds}s linear infinite;
}}
@keyframes nova-season-in {{ from {{ opacity: 0; }} }}
@keyframes nova-drift {{ to {{ background-position: {s.drift_to}; }} }}
[data-testid="stAppViewContainer"] {{ position: relative; z-index: 1; }}
[data-testid="stSidebar"] {{ background: {s.sidebar}; }}
"""


def apply_season(name: str) -> None:
    """Inject one season's look; call after theme.apply_theme()."""
    css = season_css(name)
    if css:
        st.html(f"<style>{css}</style>")


def chip(name: str, day: int, known: bool) -> None:
    """Small label naming the phase and whether it's logged or estimated."""
    s = SEASONS[name]
    source = "from your log" if known else "estimated from your cycles"
    st.html(
        f'<div class="nova-season-chip">{escape(s.icon)} <b>{escape(s.name)}</b>'
        f" · {escape(s.phase)}, day {day} · <span>{escape(source)}</span></div>"
    )


def tile(name: str) -> str:
    """HTML for a small preview tile of one season (the demo's gallery)."""
    s = SEASONS[name]
    svg, _, _ = s.scene[0]
    dots = "".join(f'<i style="background:{c}"></i>' for c in s.swatches)
    return (
        f'<div class="nova-season-tile" style="background:'
        f"radial-gradient(160px 90px at 0% 0%, {s.glow_a}, transparent 70%),"
        f"radial-gradient(160px 90px at 100% 0%, {s.glow_b}, transparent 70%),{s.page}\">"
        f'<div class="nova-season-art" style="background-image:{escape(svg)}"></div>'
        f'<div class="nova-season-name" style="color:{s.ink}">{escape(s.icon)} {escape(s.name)}</div>'
        f'<div class="nova-season-phase">{escape(s.phase)}</div>'
        f'<div class="nova-season-dots">{dots}</div></div>'
    )


# --- the seasons strip on "My phases" -------------------------------------------
# Display only: a picture of the open cycle's estimated phase windows
# (phases.current_cycle), one season each. The analysis buckets and every
# window date come from phases.py unchanged; this only draws them.

STRIP_ICONS = {"Winter": "ac_unit", "Spring": "local_florist", "Summer": "sunny", "Autumn": "eco"}
STRIP_CAPTION = (
    "A picture of your phases as seasons. Each length is estimated from your own cycles, "
    "so the edges are soft guesses, not dates — and the last stretch is wide because your "
    "next period could start anywhere in it."
)


@dataclass(frozen=True)
class Segment:
    season: str  # a key of SEASONS, or "" for the next-period range
    label: str
    days: int


def _span(a: date, b: date) -> int:
    return max(0, (b - a).days + 1)  # inclusive; 0 if the window is empty


def strip_segments(current) -> list[Segment]:
    """Segments sized in days from a phases.CurrentCycle with a prediction.
    The last one is the next-period range: still luteal, or already a new
    period — Nova can't tell which, so it's drawn apart."""
    one = timedelta(days=1)
    ovulation_from = max(current.ovulation_from, current.period_end + one)
    parts = [
        Segment("Winter", "period", _span(current.start, current.period_end)),
        Segment("Spring", "follicular", _span(current.period_end + one, current.ovulation_from - one)),
        Segment("Summer", "ovulation window", _span(ovulation_from, current.ovulation_to)),
        Segment("Autumn", "luteal", _span(current.luteal_from, current.next_earliest - one)),
        Segment("", "luteal, or your next period", _span(current.next_earliest, current.next_latest)),
    ]
    return [p for p in parts if p.days > 0]


def _icon(season: str) -> str:
    return (f'<span class="nova-icon" aria-hidden="true" style="color:{SEASONS[season].ink}">'
            f"{STRIP_ICONS[season]}</span>")


def strip_html(current) -> str:
    """The strip as HTML: bars sized by estimated days, a marker for today,
    and a legend underneath (labels don't fit inside short segments)."""
    segs = strip_segments(current)
    total = sum(s.days for s in segs)
    bars, legend = [], []
    for s in segs:
        days = f"~{s.days} day{'s' if s.days != 1 else ''}"
        if s.season:
            bars.append(f'<div class="nova-strip-seg" style="flex:{s.days};background:{SEASONS[s.season].accent}"></div>')
            legend.append(f'<span class="nova-strip-key">{_icon(s.season)}<b style="color:{SEASONS[s.season].ink}">'
                          f"{s.season}</b> {escape(s.label)} · {days}</span>")
        else:
            bars.append(f'<div class="nova-strip-seg nova-strip-range" style="flex:{s.days}"></div>')
            legend.append(f'<span class="nova-strip-key"><i class="nova-strip-swatch"></i>'
                          f"<b>Autumn or Winter</b> {escape(s.label)} · {days}</span>")
    if not any(s.season == "Spring" for s in segs):
        legend.insert(1, f'<span class="nova-strip-key">{_icon("Spring")}<b style="color:{SEASONS["Spring"].ink}">'
                      "Spring</b> follicular · inside the summer window this cycle, too uncertain to draw apart</span>")
    left = min(100.0, max(0.0, (current.day - 0.5) / total * 100))
    marker = f'<div class="nova-strip-today" style="left:{left:.1f}%"><span>today</span></div>'
    return ('<div class="nova-strip">'
            f'<div class="nova-strip-bar">{"".join(bars)}{marker}</div>'
            f'<div class="nova-strip-legend">{"".join(legend)}</div></div>')
