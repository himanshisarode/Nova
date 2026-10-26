"""Phase 7: the charts plot the right values, in the palette, or nothing."""
from datetime import date, timedelta

import charts
import db
import irregularity


def assessments(lengths, first=date(2026, 1, 1)):
    starts = [first]
    for n in lengths:
        starts.append(starts[-1] + timedelta(days=n))
    return irregularity.assess_cycles(db.cycles_from_starts(starts))


def test_cycle_length_chart_values_and_irregular_colour():
    fig = charts.cycle_length_chart(assessments([28, 30, 29, 41]))
    bar = fig.data[0]
    assert list(bar.x) == ["01 Jan 2026", "29 Jan 2026", "28 Feb 2026", "29 Mar 2026"]
    assert list(bar.y) == [28, 30, 29, 41]
    assert list(bar.marker.color) == [charts.BLUSH] * 3 + [charts.LAVENDER]
    assert bar.customdata[-1].startswith("12 days longer than your usual 29")
    assert bar.customdata[0] == "within your usual pattern"


def test_cycle_length_band_is_median_plus_minus_seven():
    fig = charts.cycle_length_chart(assessments([28, 30, 29, 41]))
    [band] = fig.layout.shapes
    # median(28, 30, 29, 41) = 29.5 -> 22.5 .. 36.5
    assert (band.y0, band.y1) == (22.5, 36.5)


def test_period_length_chart():
    fig = charts.period_length_chart([date(2026, 1, 1), date(2026, 1, 29)], [5, 4])
    assert list(fig.data[0].y) == [5, 4]
    assert list(fig.data[0].x) == ["01 Jan 2026", "29 Jan 2026"]


def test_symptom_chart_puts_most_common_on_top():
    fig = charts.symptom_frequency_chart({"fatigue": 0.25, "cramps": 1.0, "back_pain": 0.5})
    bar = fig.data[0]
    # Plotly draws horizontal bars bottom-up, so the last entry is on top.
    assert list(bar.y) == ["fatigue", "back pain", "cramps"]
    assert list(bar.x) == [0.25, 0.5, 1.0]


def test_empty_data_gives_no_chart():
    assert charts.cycle_length_chart([]) is None
    assert charts.period_length_chart([], []) is None
    assert charts.symptom_frequency_chart({}) is None


def test_charts_use_the_nova_font_and_transparent_background():
    fig = charts.cycle_length_chart(assessments([28, 30]))
    assert fig.layout.font.family.startswith("Quicksand")
    assert fig.layout.paper_bgcolor == "rgba(0,0,0,0)"


def test_flags_can_be_hidden_for_the_partner_view():
    fig = charts.cycle_length_chart(assessments([28, 30, 29, 41]), show_flags=False)
    bar = fig.data[0]
    assert list(bar.marker.color) == [charts.BLUSH] * 4
    assert bar.customdata is None
    assert "longer" not in bar.hovertemplate
