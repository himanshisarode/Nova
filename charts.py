"""Cycle Trends charts (spec.md Feature 4), in Nova's pastel palette.

Each function takes plain data and returns a Plotly figure, or None when
there's nothing to draw — the page shows a warm empty state instead of
empty axes. The cycle-length chart marks irregular cycles, so the card
it sits in must also show the medical disclaimer (spec.md).
"""
from statistics import median

import plotly.graph_objects as go

import irregularity

BLUSH = "#E58FA3"  # a touch deeper than the #F6C6CE surface blush, to read as a bar
LAVENDER = "#A88BC9"
BAND = "rgba(217, 201, 232, 0.35)"
CHARCOAL = "#3B3436"
GRID = "rgba(240, 221, 226, 0.9)"


def _style(fig: go.Figure, y_title: str | None = None) -> go.Figure:
    fig.update_layout(
        font=dict(family="Quicksand, sans-serif", color=CHARCOAL, size=13),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=8, b=8),
        height=280,
        bargap=0.35,
        showlegend=False,
        hoverlabel=dict(bgcolor="white", font_family="Quicksand, sans-serif"),
    )
    fig.update_xaxes(showgrid=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, title=y_title, rangemode="tozero")
    return fig


def cycle_length_chart(assessments: list[irregularity.CycleAssessment]) -> go.Figure | None:
    """Bars per completed cycle; irregular ones in lavender; a soft band
    for "within 7 days of your usual" (the median of all cycles shown)."""
    if not assessments:
        return None
    labels = [a.start.strftime("%d %b %Y") for a in assessments]
    lengths = [a.length for a in assessments]
    fig = go.Figure(go.Bar(
        x=labels,
        y=lengths,
        marker=dict(color=[LAVENDER if a.irregular else BLUSH for a in assessments],
                    cornerradius=8),
        customdata=[a.reason or "within your usual pattern" for a in assessments],
        hovertemplate="%{x}<br><b>%{y} days</b><br>%{customdata}<extra></extra>",
    ))
    usual = median(lengths)
    fig.add_hrect(
        y0=usual - irregularity.MAX_DEVIATION_DAYS, y1=usual + irregularity.MAX_DEVIATION_DAYS,
        fillcolor=BAND, line_width=0, layer="below",
    )
    return _style(fig, "Days")


def period_length_chart(starts: list, period_days: list[int]) -> go.Figure | None:
    """Bleeding days per cycle."""
    if not starts:
        return None
    fig = go.Figure(go.Bar(
        x=[s.strftime("%d %b %Y") for s in starts],
        y=period_days,
        marker=dict(color=BLUSH, cornerradius=8),
        hovertemplate="%{x}<br><b>%{y} days</b><extra></extra>",
    ))
    return _style(fig, "Period days")


def symptom_frequency_chart(shares: dict[str, float]) -> go.Figure | None:
    """Horizontal bars: share of cycles with each symptom, most common on top."""
    if not shares:
        return None
    ordered = sorted(shares.items(), key=lambda kv: kv[1])  # plotly draws bottom-up
    fig = go.Figure(go.Bar(
        x=[share for _, share in ordered],
        y=[name.replace("_", " ") for name, _ in ordered],
        orientation="h",
        marker=dict(color=LAVENDER, cornerradius=8),
        hovertemplate="%{y}: <b>%{x:.0%}</b> of cycles<extra></extra>",
    ))
    _style(fig)
    fig.update_xaxes(tickformat=".0%", range=[0, 1], gridcolor=GRID, showgrid=True)
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    fig.update_layout(height=max(180, 36 * len(ordered) + 40))
    return fig
