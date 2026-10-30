"""Faint corner line art for every page: botanicals, a moon, sparkles.

Original drawings, built here from simple shapes (no files, no links).
They sit in the background of the main area and the sidebar as CSS
background images, so they can't catch clicks, never move, and stay
behind every card. Strokes are thin and low-opacity so text keeps its
contrast. One piece per screen region: top-right and bottom-left of the
page, bottom of the sidebar.
"""
import math
from urllib.parse import quote

INK = "#D58A9C"  # a deeper blush, used at low opacity
OPACITY = 0.42


def _url(body: str, w: int, h: int) -> str:
    svg = (
        f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}' "
        f"fill='none' stroke='{INK}' stroke-width='1.6' stroke-linecap='round' "
        f"stroke-linejoin='round' opacity='{OPACITY}'>{body}</svg>"
    )
    return f'url("data:image/svg+xml,{quote(svg, safe=" =:/,\'")}")'


def _sparkle(x: float, y: float, r: float) -> str:
    """A four-pointed star with curved sides."""
    return (f"<path d='M{x} {y - r} Q{x} {y} {x + r} {y} Q{x} {y} {x} {y + r} "
            f"Q{x} {y} {x - r} {y} Q{x} {y} {x} {y - r} Z'/>")


def _leaf(x: float, y: float, length: float, angle: float) -> str:
    """A simple pointed leaf with a centre vein, growing from (x, y)."""
    w = length * 0.38
    return (f"<g transform='translate({x} {y}) rotate({angle})'>"
            f"<path d='M0 0 Q{length / 2} {-w} {length} 0 Q{length / 2} {w} 0 0 Z'/>"
            f"<path d='M{length * 0.12} 0 L{length * 0.8} 0' opacity='0.6'/></g>")


def _flower(x: float, y: float, r: float, petals: int = 5) -> str:
    parts = []
    for k in range(petals):
        a = 360 / petals * k
        parts.append(f"<ellipse cx='{x}' cy='{y - r}' rx='{r * 0.45:.1f}' ry='{r * 0.85:.1f}' "
                     f"transform='rotate({a:.0f} {x} {y})'/>")
    parts.append(f"<circle cx='{x}' cy='{y}' r='{r * 0.28:.1f}'/>")
    return "".join(parts)


def _crescent(cx: float, cy: float, r: float) -> str:
    """Outer arc, then a shallower inner arc back: a waxing crescent."""
    top = (cx + r * math.cos(math.radians(-60)), cy + r * math.sin(math.radians(-60)))
    bottom = (cx + r * math.cos(math.radians(60)), cy + r * math.sin(math.radians(60)))
    return (f"<path d='M{top[0]:.1f} {top[1]:.1f} A{r} {r} 0 1 0 {bottom[0]:.1f} {bottom[1]:.1f} "
            f"A{r * 0.8:.1f} {r * 0.8:.1f} 0 1 1 {top[0]:.1f} {top[1]:.1f} Z'/>")


def moon_sprig() -> str:
    """Top right: a crescent, three sparkles and a trailing sprig."""
    body = (
        _crescent(150, 62, 30)
        + _sparkle(206, 38, 7) + _sparkle(96, 30, 5) + _sparkle(214, 104, 4)
        + "<path d='M250 120 C200 128 160 150 128 190'/>"
        + _leaf(226, 124, 26, -150) + _leaf(200, 133, 24, -205)
        + _leaf(176, 145, 24, -140) + _leaf(156, 160, 22, -210)
        + _leaf(140, 176, 20, -135)
    )
    return _url(body, 260, 210)


def botanical() -> str:
    """Bottom left: two stems with leaves, one flower, a bud."""
    body = (
        "<path d='M60 260 C62 210 52 170 70 120'/>"
        + _flower(72, 104, 14)
        + _leaf(60, 220, 30, -30) + _leaf(58, 190, 28, -150)
        + _leaf(62, 160, 26, -35)
        + "<path d='M60 260 C90 230 110 205 118 168'/>"
        + "<path d='M118 168 q-8 -14 0 -26 q8 12 0 26 Z'/>"
        + _leaf(98, 214, 22, -70) + _leaf(110, 192, 20, -10)
        + _sparkle(150, 130, 5) + _sparkle(28, 96, 4)
    )
    return _url(body, 180, 270)


def small_moon() -> str:
    """Sidebar foot: a small crescent over a single leafy stem."""
    body = (
        _crescent(46, 34, 16) + _sparkle(82, 22, 5)
        + "<path d='M30 120 C40 100 60 90 90 84'/>"
        + _leaf(48, 99, 18, -110) + _leaf(66, 90, 18, -20) + _leaf(80, 86, 14, -100)
    )
    return _url(body, 120, 130)


def corner_css() -> str:
    return f"""
[data-testid="stMain"] {{
  background-image: {moon_sprig()}, {botanical()};
  background-position: right 18px top 52px, left 0 bottom 0;
  background-size: 240px auto, 130px auto;
  background-repeat: no-repeat;
}}
[data-testid="stSidebarContent"] {{
  background-image: {small_moon()};
  background-position: left 20px bottom 20px;
  background-size: 120px auto;
  background-repeat: no-repeat;
}}
"""
