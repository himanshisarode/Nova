"""Throwaway Phase 0 demo page (PLAN.md Phase 0) — shows the design system
with sample content only. Nothing here is saved or computed; delete this
file once the look is approved and real pages exist.

Run: streamlit run design_demo.py

The sidebar's "Preview a season" switches the phase-tinted background
(seasons.py) so all four can be compared before it reaches the real app.
"""
from datetime import date

import pandas as pd
import streamlit as st

import seasons
from theme import apply_theme, card, empty_state, eyebrow, footer, medical_disclaimer

st.set_page_config(page_title="Nova", page_icon="🌙", layout="centered")
apply_theme()

# Sample cycle position per season: (cycle day, next period in, logged?).
# Only the period is known from the log; the other phases are estimates.
SAMPLE_DAY = {
    seasons.NEUTRAL: (12, "14–19 days", True),
    "Winter": (2, "25–30 days", True),
    "Spring": (9, "17–22 days", False),
    "Summer": (14, "12–17 days", False),
    "Autumn": (22, "4–9 days", False),
}
GREETING_EMOJI = {seasons.NEUTRAL: "🌸", "Winter": "🫖", "Spring": "🌷", "Summer": "🌻", "Autumn": "🍂"}

with st.sidebar:
    st.markdown("### 🌙 Nova")
    st.caption("Your cycle, gently tracked.")
    st.radio(
        "Pages",
        ["Today", "Cycle Trends", "Insights", "Did You Know?", "Settings"],
        label_visibility="collapsed",
    )
    st.divider()
    options = [seasons.NEUTRAL, *seasons.SEASONS]
    start = st.query_params.get("season", "Spring")  # ?season=Winter for screenshots
    season = st.radio(
        "Preview a season",
        options,
        index=options.index(start) if start in options else 2,
        format_func=lambda n: n if n == seasons.NEUTRAL else f"{seasons.SEASONS[n].icon} {n}",
    )
    tinted = st.toggle("Phase-tinted background", value=True)
    st.caption("Design preview — sample data only.")

look = season if tinted else seasons.NEUTRAL
seasons.apply_season(look)
day, next_period, from_log = SAMPLE_DAY[season]

# --- Welcome -----------------------------------------------------------------
with card("welcome", tone="blush"):
    eyebrow(date.today().strftime("%A, %d %B"))
    st.markdown(f"# Good to see you, Maya {GREETING_EMOJI[look]}")
    st.markdown(
        "Take a breath. Logging today takes about a minute, and every entry "
        "helps Nova get to know your rhythm a little better."
    )
    if look != seasons.NEUTRAL:
        seasons.chip(look, day, known=from_log)

# --- At a glance -------------------------------------------------------------
with card("glance"):
    eyebrow("At a glance")
    st.markdown("### Where you are this cycle")
    c1, c2, c3 = st.columns(3)
    c1.metric("Cycle day", str(day))
    c2.metric("Next period in", next_period)
    c3.metric("Cycles logged", "4")
    st.caption(
        "Predictions show a range, not a single date — that range is Nova "
        "being honest about how much it can know so far."
    )
    medical_disclaimer()

# --- Season gallery ----------------------------------------------------------
with card("seasons"):
    eyebrow("Seasons preview")
    st.markdown("### Your background follows your cycle")
    for col, name in zip(st.columns(4), seasons.SEASONS):
        col.html(seasons.tile(name))
    st.caption(
        "The colours are a mood, not a forecast of how you'll feel. Only the "
        "period is read from your log; the other phases are estimates, and "
        "you can switch this off in Settings."
    )

# --- Daily log ---------------------------------------------------------------
with card("log"):
    eyebrow("Today's check-in")
    st.markdown("### How are you feeling?")
    with st.form("demo_log"):
        left, right = st.columns(2)
        left.selectbox("Flow", ["none", "light", "medium", "heavy"])
        right.select_slider(
            "Mood",
            options=["😣", "😕", "😐", "🙂", "😊"],
            value="🙂",
        )
        st.multiselect(
            "Anything you noticed?",
            ["cramps", "headache", "bloating", "fatigue", "acne", "tender breasts"],
            default=["fatigue"],
            placeholder="Pick as many as you like, or none",
        )
        st.markdown("**Lifestyle** *(optional)*")
        t1, t2, t3 = st.columns(3)
        t1.checkbox("Poor sleep")
        t2.checkbox("High stress", value=True)
        t3.checkbox("Travel")
        with st.expander("Tried something for a symptom? (optional)"):
            r1, r2 = st.columns([2, 1])
            r1.text_input("What helped (or didn't)", placeholder="e.g. heat pad, a walk, tea")
            r2.slider("Relief", 1, 5, 4)
        st.text_area("A note for yourself", placeholder="Anything on your mind today…")
        submitted = st.form_submit_button("Save today's entry", type="primary")
    if submitted:
        st.toast("This is just a design preview — nothing was saved. 🌷")

# --- Trends ------------------------------------------------------------------
with card("trends", tone="lavender"):
    eyebrow("Cycle Trends")
    st.markdown("### Your last few cycles")
    sample = pd.DataFrame(
        {"Cycle length (days)": [29, 31, 28, 30]},
        index=["Jun", "Jul", "Aug", "Sep"],
    )
    st.bar_chart(sample, height=220, sort=False, x_label="", y_label="Days")
    st.info("Your cycles have stayed within a 3-day range — nice and steady. 💜")

# --- Insights (empty states) -------------------------------------------------
with card("insights"):
    eyebrow("Insights")
    st.markdown("### Patterns we're watching for")
    tab_link, tab_remedy = st.tabs(["Lifestyle links", "What helps"])
    with tab_link:
        empty_state(
            icon="🌱",
            title="Still getting to know you",
            body=(
                "Once you've logged a few more cycles with and without high stress, "
                "Nova can check whether stress seems to shift your cycle length. "
                "No rush — every check-in counts."
            ),
            have=2,
            need=3,
        )
    with tab_remedy:
        empty_state(
            icon="🫖",
            title="Your comfort notes will gather here",
            body=(
                "Log what you try for cramps or headaches, and after a few tries "
                "Nova will show which ones tend to bring you the most relief."
            ),
            have=1,
            need=3,
        )

# --- Did you know ------------------------------------------------------------
with card("dyk", tone="blush"):
    eyebrow("Did you know?")
    with st.expander("Is a 'normal' cycle exactly 28 days?"):
        st.markdown(
            "Not usually! Healthy cycles commonly range from about 21 to 35 days, "
            "and a few days of variation from month to month is normal."
        )
        st.caption(
            "General education, not personal medical advice — if something feels "
            "off for you, a doctor is always a good person to ask."
        )

# --- Alert palette check ----------------------------------------------------
with card("alerts"):
    eyebrow("Message styles")
    st.success("Entry saved — thank you for checking in. 🌿")
    st.warning("Your last log was 5 days ago. Whenever you're ready, we're here.")
    st.error("Something went wrong saving that — your entry is still here, try again?")

footer()
