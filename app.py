"""Nova — the Streamlit app (PLAN.md Phase 8). Run: streamlit run app.py

Wires the modules into pages. Logic lives in the modules; this file only
decides what to show. Every prediction, fertile-window estimate and
irregularity flag sits in a card that also carries the medical
disclaimer, and every page ends with the disclaimer footer (spec.md).

The database file is data/nova.db, or NOVA_DB_PATH if set (Docker mounts
a volume there). A connection is opened per script run.
"""
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

import auth
import charts
import db
import demo
import export
import gate
import irregularity
import lifestyle_link
import partner
import phase_guide
import phases
import predict
import qna_content
import remedy
import week_fit
import whatworks
from theme import apply_theme, card, empty_state, eyebrow, footer, medical_disclaimer

DB_PATH = db.db_path()
PAGES = ("Today", "Home", "My phases", "Plan my week", "Cycle Trends", "Insights",
         "Did You Know?", "Shared with me", "Settings")
RATING_LABELS = {1: "😣 1", 2: "😕 2", 3: "😐 3", 4: "🙂 4", 5: "😊 5"}
# Demo visitors opt in to the LLM features per tab, never in the shared account.
DEMO_OPT_IN = {"phase_guide": "demo_opt_in_phase_guide", "week_fit": "demo_opt_in_week_fit"}
NOT_RECORDED = "not recorded"
MOOD_LABELS = {NOT_RECORDED: "not recorded", 1: "😣 1", 2: "😕 2", 3: "😐 3", 4: "🙂 4", 5: "😊 5"}


def _fmt(d: date) -> str:
    return d.strftime("%a %d %b")


def _label(name: str) -> str:
    return name.replace("_", " ")


# --- shared pieces ------------------------------------------------------------

def prediction_card(name: str, lengths: list[int], last_start: date | None, today: date, mode: str) -> None:
    """Next-period card (own Home page and the partner view)."""
    with card(name, tone="blush"):
        eyebrow("Next period")
        if last_start is None or len(lengths) < predict.MIN_CYCLES:
            empty_state(
                icon="🌙",
                title="Getting to know the rhythm",
                body=(
                    f"Predictions start once {predict.MIN_CYCLES} cycles are complete — "
                    "until then Nova would only be guessing, and it would rather be honest."
                ),
                have=len(lengths),
                need=predict.MIN_CYCLES,
            )
        else:
            p = (predict.honest_prediction if mode == "Honest" else predict.simple_prediction)(lengths, last_start)
            if predict.is_late(p, today):
                st.markdown("### Later than the usual range")
                st.markdown(
                    "Your period hasn't been logged yet and it's now past the range your "
                    "past cycles suggest. That happens — stress, travel or illness can shift "
                    "a cycle. If there's any chance you could be pregnant, a test is the "
                    "quickest way to know."
                )
            elif isinstance(p, predict.HonestPrediction):
                st.markdown(f"### Between {_fmt(p.earliest)} and {_fmt(p.latest)}")
                st.caption(
                    f"A 90% range from your last {p.n_cycles} cycles — wider when your cycles "
                    "vary more, narrower as they settle."
                )
            else:
                st.markdown(f"### Around {_fmt(p.next_start)}")
                st.caption(f"Your last period start plus your average cycle ({p.mean_length:.1f} days).")
        medical_disclaimer()


def mode_toggle() -> str:
    return st.segmented_control(
        "Prediction style", ["Honest", "Simple"], default="Honest", key="mode",
        help="Honest shows a range that reflects how much your cycles vary. Simple shows one date.",
    ) or "Honest"


# --- pages ----------------------------------------------------------------------

def page_login(conn) -> None:
    with card("welcome", tone="blush"):
        st.markdown("# 🌙 Nova")
        st.markdown("Your cycle, gently tracked — with predictions that are honest about what they know.")
    with card("auth"):
        log_in, sign_up = st.tabs(["Log in", "Create account"])
        with log_in, st.form("login"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Log in", type="primary"):
                user = auth.login(conn, email, password)
                if user:
                    auth.start_session(user)
                    st.rerun()
                st.error("That email and password don't match an account. Want to try again?")
        with sign_up, st.form("signup"):
            name = st.text_input("What should we call you?", key="signup_name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input(
                "Password", type="password", key="signup_password",
                help=f"At least {auth.MIN_PASSWORD_LENGTH} characters.",
            )
            if st.form_submit_button("Create account", type="primary"):
                try:
                    auth.start_session(auth.signup(conn, email, password, name))
                    st.rerun()
                except auth.SignupError as exc:
                    st.error(str(exc))
    with card("demo-entry", tone="lavender"):
        st.markdown("**Just looking?** Explore Nova with nine months of made-up sample data — "
                    "the personal findings and plans included.")
        if st.button("Try the demo", key="try_demo"):
            auth.start_session(demo.ensure_demo(conn))
            st.rerun()


def page_today(conn, user: auth.User, today: date) -> None:
    with card("welcome", tone="blush"):
        eyebrow(today.strftime("%A, %d %B"))
        st.markdown(f"# Hi {user.display_name} 🌸")
        st.markdown("Logging takes about a minute, and every entry helps Nova know your rhythm a little better.")

    with card("log"):
        eyebrow("Check-in")
        day = st.date_input("Which day?", value=today, max_value=today, key="log_day")
        existing = db.get_log(conn, user.id, day) or db.LogEntry(day)
        k = day.isoformat()  # fresh widgets per day, pre-filled from that day's log
        with st.form(f"log_{k}"):
            left, right = st.columns(2)
            flow_options = [NOT_RECORDED, *db.FLOW_LEVELS]
            flow = left.selectbox("Flow", flow_options, index=flow_options.index(existing.flow or NOT_RECORDED), key=f"flow_{k}")
            mood = right.select_slider(
                "Mood", options=list(MOOD_LABELS), value=existing.mood or NOT_RECORDED,
                format_func=MOOD_LABELS.get, key=f"mood_{k}",
            )
            symptoms = st.multiselect(
                "Anything you noticed?", db.SYMPTOMS, default=sorted(existing.symptoms),
                format_func=_label, placeholder="Pick as many as you like, or none", key=f"symptoms_{k}",
            )
            st.markdown("**Lifestyle** *(optional)*")
            cols = st.columns(len(db.LIFESTYLE_TAGS))
            tags = {
                t: col.checkbox(_label(t).capitalize(), value=getattr(existing, t), key=f"{t}_{k}")
                for t, col in zip(db.LIFESTYLE_TAGS, cols)
            }
            st.markdown("**What works for me** *(optional — a few taps)*")
            strategies = st.pills(
                "Tried today", db.STRATEGIES, selection_mode="multi",
                default=sorted(existing.strategies), format_func=_label, key=f"strategies_{k}",
            )
            q1, q2 = st.columns(2)
            day_rating = q1.segmented_control(
                "How did today go?", list(RATING_LABELS), default=existing.day_rating,
                format_func=RATING_LABELS.get, key=f"day_rating_{k}",
            )
            energy = q2.segmented_control(
                "Energy", list(RATING_LABELS), default=existing.energy,
                format_func=RATING_LABELS.get, key=f"energy_{k}",
            )
            with st.expander("Tried something for a symptom? (optional)"):
                r1, r2, r3 = st.columns([2, 3, 2])
                r_symptom = r1.selectbox("For", [None, *db.SYMPTOMS], format_func=lambda s: "—" if s is None else _label(s), key=f"r_symptom_{k}")
                r_text = r2.text_input("What you tried", placeholder="e.g. heat pad, a walk, tea", key=f"r_text_{k}")
                r_rating = r3.slider("Relief", 1, 5, 3, key=f"r_rating_{k}")
                past = db.past_remedies(conn, user.id)
                if past:
                    st.caption("You've tried before: " + ", ".join(_label(p) for p in past[:8]))
            if st.form_submit_button("Save this day", type="primary"):
                try:
                    db.save_log(conn, user.id, db.LogEntry(
                        day, flow=None if flow == NOT_RECORDED else flow,
                        mood=None if mood == NOT_RECORDED else mood,
                        symptoms=frozenset(symptoms), **tags,
                        day_rating=day_rating, energy=energy, strategies=frozenset(strategies or ()),
                    ))
                except db.DemoReadOnly as exc:
                    st.info(str(exc))
                    return
                if r_text.strip():
                    if r_symptom is None:
                        st.warning("Day saved. To save the remedy too, pick which symptom it was for.")
                    else:
                        db.add_remedy(conn, user.id, day, r_symptom, r_text, r_rating)
                st.toast("Saved — thank you for checking in. 🌷")


def page_home(conn, user: auth.User, today: date) -> None:
    cycles = db.get_cycles(conn, user.id)
    starts = db.get_period_starts(conn, user.id)
    lengths = [c.length for c in cycles]
    last = starts[-1] if starts else None

    with card("glance"):
        eyebrow("At a glance")
        st.markdown(f"### Welcome back, {user.display_name}")
        c1, c2 = st.columns(2)
        c1.metric("Cycle day", (today - last).days + 1 if last else "—")
        c2.metric("Completed cycles", len(cycles))

    mode = mode_toggle()
    prediction_card("prediction", lengths, last, today, mode)

    with card("fertile", tone="lavender"):
        eyebrow("Fertile window — an estimate, not contraception")
        if last is None or len(lengths) < predict.MIN_CYCLES:
            empty_state(
                icon="🌿", title="Not enough cycles yet",
                body="The fertile-window estimate appears alongside your period prediction.",
                have=len(lengths), need=predict.MIN_CYCLES,
            )
        elif predict.varies_a_lot(lengths):
            recent = lengths[-predict.MAX_CYCLES_USED:]
            st.markdown("### Worth a chat with a doctor")
            st.markdown(
                f"Your recent cycles have ranged from {min(recent)} to {max(recent)} days — "
                f"a spread of {predict.cycle_variation(lengths)} days. With that much variation, "
                "a fertile-window estimate would cover most of your cycle, so Nova won't show one. "
                "Cycles that vary this much are worth mentioning to a doctor or gynecologist: "
                "often there's a simple explanation, and they can help you find it."
            )
        else:
            p = (predict.honest_prediction if mode == "Honest" else predict.simple_prediction)(lengths, last)
            luteal_days = phases.luteal(db.get_settings(conn, user.id).luteal_days)
            w = predict.fertile_window(p, luteal_days)
            st.markdown(f"### {_fmt(w.start)} – {_fmt(w.end)}")
            st.caption(
                f"Estimated as {luteal_days} days before your predicted period, give or take. "
                "Never rely on this to prevent pregnancy."
            )
        medical_disclaimer()


def page_trends(conn, user: auth.User) -> None:
    cycles = db.get_cycles(conn, user.id)
    assessments = irregularity.assess_cycles(cycles)
    report = export.build_doctor_report(conn, user.id, months=None)

    with card("trend-length"):
        eyebrow("Cycle length")
        fig = charts.cycle_length_chart(assessments)
        if fig is None:
            empty_state(icon="📈", title="Your first chart is on its way",
                        body="Once a cycle is complete, its length shows up here.")
        else:
            st.plotly_chart(fig, use_container_width=True, key="chart_length")
            st.caption("Lavender bars are cycles flagged as irregular — see Insights for what happened.")
        medical_disclaimer()

    with card("trend-period"):
        eyebrow("Period length")
        fig = charts.period_length_chart([r.start for r in report.rows], [r.period_days for r in report.rows])
        if fig is None:
            empty_state(icon="🩸", title="Nothing to show just yet",
                        body="Period lengths appear here for each completed cycle.")
        else:
            st.plotly_chart(fig, use_container_width=True, key="chart_period")

    with card("trend-symptoms"):
        eyebrow("Symptoms")
        fig = charts.symptom_frequency_chart(report.symptom_share())
        if fig is None:
            empty_state(icon="🫶", title="No symptoms logged in completed cycles yet",
                        body="When you log symptoms, you'll see how often each one shows up.")
        else:
            st.plotly_chart(fig, use_container_width=True, key="chart_symptoms")


@st.cache_data(show_spinner="Looking for patterns…")
def _explain(assessments, features):
    return irregularity.explain_flags(list(assessments), list(features))


def page_insights(conn, user: auth.User) -> None:
    cycles = db.get_cycles(conn, user.id)
    logs = db.get_logs(conn, user.id)
    assessments = irregularity.assess_cycles(cycles)
    flagged = [a for a in assessments if a.irregular]

    with card("flags"):
        eyebrow("Irregular cycles")
        if not cycles:
            empty_state(icon="🌱", title="Still getting to know you",
                        body="Once cycles are complete, Nova checks each one against the typical range and your own usual.")
        elif not flagged:
            st.markdown(f"None of your {len(cycles)} completed cycles stood out. 💜")
        else:
            st.markdown(f"**{len(flagged)} of {len(cycles)}** completed cycles stood out:")
            for a in flagged:
                st.markdown(f"- **{a.start.strftime('%d %b %Y')}**: {a.message}")
            result = _explain(tuple(assessments), tuple(irregularity.cycle_features(cycles, logs)))
            if isinstance(result, irregularity.NotEnoughFlags):
                st.caption(
                    f"Nova looks for logged factors that go with irregular cycles once there are at least "
                    f"{result.need} irregular and {result.need} regular ones."
                )
            else:
                explained = [e for e in result if e.factors]
                st.caption(explained[0].message if explained else
                           "No logged factor stood out clearly enough to mention.")
        medical_disclaimer()

    with card("links", tone="lavender"):
        eyebrow("Lifestyle links")
        rows = lifestyle_link.cycles_with_tags(cycles, logs)
        for tag, result in lifestyle_link.all_links(rows).items():
            if result["status"] == "not_enough_data":
                have = min(result["n_with"], result["n_without"])
                st.markdown(f"**{_label(tag).capitalize()}** — {lifestyle_link.describe(result, tag)}")
                st.progress(min(1.0, have / lifestyle_link.MIN_PER_GROUP))
            else:
                st.markdown(f"**{_label(tag).capitalize()}** — {lifestyle_link.describe(result, tag)}")
        st.caption("A link here is a pattern in your own logs, not proof of a cause.")

    with card("remedies"):
        eyebrow("What helps")
        logs_for_stats = [
            {"symptom": r.symptom, "remedy": r.remedy, "relief_rating": r.relief_rating}
            for r in db.get_remedies(conn, user.id)
        ]
        results = remedy.remedy_effectiveness(logs_for_stats)
        if not results:
            empty_state(icon="🫖", title="Your comfort notes will gather here",
                        body="Log what you try for a symptom on the Today page, and after a few tries "
                             "Nova will show which ones tend to bring you the most relief.")
        for symptom, entries in results.items():
            st.markdown(f"**{_label(symptom).capitalize()}**")
            for entry in entries:
                st.markdown(f"- {remedy.describe(entry)}")


# --- Level 2: phases, what works, Phase Guide, Week Fit ----------------------------

CONTRACEPTION_CAVEAT = (
    "You've said you use hormonal contraception. That usually means there's no natural cycle "
    "for these phases to describe, so Nova shows only your bleeding pattern here and keeps the "
    "personal findings, Phase Guide and Plan my week switched off."
)
LIMITS = (
    "These are patterns in your own logs, not causes: you choose what to do by feel (a good day "
    "may lead to the walk, not the other way round), days close together affect each other, and "
    "phases are calendar estimates."
)


@st.cache_data(show_spinner="Looking at what tends to go well…")
def _analyse(days):
    return whatworks.analyse(list(days))


def level2_context(conn, user: auth.User, today: date) -> dict:
    """Everything the Level 2 pages need, computed once per run."""
    logs = db.get_logs(conn, user.id)
    cycles = db.get_cycles(conn, user.id)
    starts = db.get_period_starts(conn, user.id)
    bleeding = [e.date for e in logs if e.flow in db.BLEEDING_FLOWS]
    settings = db.get_settings(conn, user.id)
    lengths = [c.length for c in cycles]
    period_days = phases.typical_period_days(starts, bleeding)
    status = gate.gate_status([e.date for e in logs], len(cycles), today)
    personal = status.open and not settings.hormonal_contraception
    results = _analyse(tuple(whatworks.rated_days(starts, logs, settings.luteal_days))) if personal else []
    recent = lengths[-predict.MAX_CYCLES_USED:]
    return dict(
        logs=logs, cycles=cycles, settings=settings, gate=status, personal=personal,
        current=phases.current_cycle(starts, bleeding, lengths, today, settings.luteal_days, period_days),
        period_days=period_days, results=results, findings=whatworks.goes_well(results),
        cycle_range=(min(recent), max(recent)) if recent else (0, 0),
    )


def _session_opt_in(settings: db.Settings, call_type: str) -> bool:
    return settings.is_demo and st.session_state.get(DEMO_OPT_IN[call_type], False)


def gate_card(ctx: dict) -> None:
    with card("gate", tone="lavender"):
        eyebrow("Your personal findings")
        st.markdown("### Getting to know what works for you")
        st.markdown(
            "Nova learns what tends to go well for you in each phase from your own log — never "
            "from generic tips. That needs about six months of logging first, so the patterns "
            "are yours and not chance."
        )
        for c in ctx["gate"].conditions:
            st.markdown(f"**{c.label.capitalize()}** — {min(c.have, c.need)} of {c.need}")
            st.progress(min(1.0, c.have / c.need))
        st.caption("Rating how each day went (on the Today page) is what these findings are built from.")


def page_phases(conn, user: auth.User, today: date) -> None:
    ctx = level2_context(conn, user, today)
    settings, current = ctx["settings"], ctx["current"]

    with card("phase-tracker", tone="blush"):
        eyebrow("Your phases — estimates from your own cycles")
        if settings.hormonal_contraception:
            st.info(CONTRACEPTION_CAVEAT)
        if current is None:
            empty_state(icon="🌙", title="Your phases appear after your first period",
                        body="Log a period on the Today page and Nova will start placing your phases.")
        elif not current.enough_data:
            st.markdown(f"### Day {current.day} of your cycle")
            st.markdown("Period days come straight from your log. The other phases need "
                        f"{predict.MIN_CYCLES} completed cycles before Nova can estimate them.")
        elif current.late:
            st.markdown(f"### Day {current.day} — luteal or a new period, not sure")
            st.markdown("Your period is later than your usual range, so Nova won't guess the phase.")
        else:
            if current.phase_today == "ovulation_window":
                st.markdown(f"### Day {current.day} · probably in your ovulation window")
            else:
                name = phases.PHASE_LABELS[current.phase_today].lower()
                st.markdown(f"### Day {current.day} · probably your {name} phase")
            st.markdown(
                f"- Ovulation window (estimate): **{_fmt(current.ovulation_from)} – {_fmt(current.ovulation_to)}**\n"
                f"- Luteal phase (estimate): from about **{_fmt(current.luteal_from)}**\n"
                f"- Next period: between **{_fmt(current.next_earliest)}** and **{_fmt(current.next_latest)}**"
            )
            st.caption(
                f"Counted back {phases.luteal(settings.luteal_days)} days from your predicted period "
                "(the luteal half is the steadier one), so the windows are as wide as the uncertainty "
                "in that prediction. You can change the luteal length in Settings."
            )
        medical_disclaimer()

    if settings.hormonal_contraception:
        return
    if not ctx["gate"].open:
        gate_card(ctx)
        return

    with card("what-works"):
        eyebrow("What works for me, by phase")
        tested = [r for r in ctx["results"] if r.tested]
        shown = [r for r in tested if r.verdict != "no_clear_difference"]
        if not tested:
            empty_state(icon="🫶", title="Not enough rated days yet",
                        body=f"A finding needs {whatworks.MIN_USES} days with a strategy in one phase, "
                             f"over {whatworks.MIN_CYCLES} cycles. Keep rating your days on the Today page.")
        for r in shown:
            st.markdown(f"- {whatworks.describe(r)}")
        if tested and not shown:
            st.markdown("Nothing stands out clearly yet — that's an honest answer, not a failure.")
        if tested:
            waiting = sum(not r.tested for r in ctx["results"])
            st.caption(f"Checked {len(tested)} strategy–phase pairs with enough data; "
                       f"{waiting} still need more days. {LIMITS}")
        medical_disclaimer()

    with card("phase-guide", tone="lavender"):
        eyebrow("Your Phase Guide")
        cycle_start = ctx["cycles"][-1].start
        session_opt_in = _session_opt_in(settings, "phase_guide")
        guide = phase_guide.stored(conn, user.id, cycle_start)
        may_write = phase_guide.allowed(settings, True, session_opt_in)
        if guide is None and may_write and st.button("Write my Phase Guide", key="write_guide"):
            guide = phase_guide.generate(conn, user.id, ctx["findings"], ctx["cycle_range"], cycle_start,
                                         gate_open=True, session_opt_in=session_opt_in)
        if guide is None:
            guide = phase_guide.template(ctx["findings"], ctx["cycle_range"])
            if not may_write:
                st.caption("This is the plain version. Turn on the written Phase Guide in Settings if you'd like it.")
        if guide.notice:
            st.caption(guide.notice)
        for name, text in guide.sections:
            st.markdown(f"**{name}** — {text}")
        st.markdown(guide.cycle_sentence)
        if guide.source == "llm":
            st.caption("Written by an AI assistant from your findings only, and checked by Nova before showing.")
        medical_disclaimer()


def page_week(conn, user: auth.User, today: date) -> None:
    ctx = level2_context(conn, user, today)
    settings = ctx["settings"]
    if settings.hormonal_contraception:
        with card("week-off"):
            st.info(CONTRACEPTION_CAVEAT)
        return
    if not ctx["gate"].open:
        gate_card(ctx)
        return
    plans = week_fit.plan_days(today, ctx["current"], ctx["period_days"], ctx["findings"], settings.luteal_days)
    session_opt_in = _session_opt_in(settings, "week_fit")
    opted_in = week_fit.allowed(settings, True, session_opt_in)

    with card("week", tone="blush"):
        eyebrow("Plan my week")
        st.markdown("### Fitting what works for you around your real week")
        if not opted_in:
            st.caption("This is the plain version from your findings. To fit them around notes about your "
                       "week, turn on Plan my week in Settings.")
            result = week_fit.template(plans)
        else:
            st.caption(week_fit.NOTICE)
            with st.form("week_notes"):
                notes = [
                    st.text_input(p.day_name, max_chars=week_fit.MAX_NOTE_CHARS,
                                  placeholder="e.g. report due, early lecture", key=f"note_{k}")
                    for k, p in enumerate(plans)
                ]
                submitted = st.form_submit_button("Fit my week", type="primary")
            result = st.session_state.get("week_fit_result")
            if submitted:
                try:
                    result = week_fit.generate(conn, user.id, plans, notes, gate_open=True,
                                               session_opt_in=session_opt_in)
                    st.session_state["week_fit_result"] = result  # this tab only; never stored
                except week_fit.NoteRejected as exc:
                    st.error(str(exc))
                    result = None
            if result is None or [d.day_name for d in result.days] != [p.day_name for p in plans]:
                result = week_fit.template(plans)
        if result.notice:
            st.caption(result.notice)
        for plan, day in zip(plans, result.days):
            where = " or ".join(phase_guide.PHASE_NAMES[b].lower() for b in phases.BUCKETS
                                if plan.buckets and b in plan.buckets) or "phase unknown"
            st.markdown(f"**{day.day_name}** · *{where} (estimate)*")
            if day.note:
                st.caption(f"Your note: {day.note}")
            st.markdown(day.sentence)
        medical_disclaimer()


def page_qna() -> None:
    with card("qna-intro", tone="blush"):
        eyebrow("Did you know?")
        st.markdown("### Common questions, gently answered")
    if not qna_content.QNA:
        with card("qna-empty"):
            empty_state(icon="📖", title="These are being written",
                        body="Short answers to common cycle questions are on their way.")
        return
    with card("qna"):
        i = 0
        for title, items in qna_content.SECTIONS:
            st.markdown(f"#### {title}")
            for item in items:
                with st.expander(item["question"], key=f"qna_{i}"):
                    st.markdown(item["answer"])
                    st.caption(qna_content.EDUCATION_LABEL)
                i += 1


def page_shared(conn, user: auth.User, today: date) -> None:
    owners = [
        l.owner_id for l in partner.links_for(conn, user.id)
        if l.viewer_id == user.id and l.status == "accepted"
    ]
    if not owners:
        with card("shared-empty"):
            empty_state(icon="💌", title="Nothing shared with you yet",
                        body="If someone shares their cycle with you, enter their invite code in Settings.")
        return
    names = {o: auth.get_user(conn, o).display_name for o in owners}
    owner = st.selectbox("Whose cycle?", owners, format_func=names.get, key="shared_owner")
    try:
        with partner.PartnerView(DB_PATH, user.id, owner) as view:
            cycles = view.cycles()
            last = view.last_period_start()
    except partner.PartnerAccessError:
        st.info("This is no longer shared with you.")
        return
    st.caption(f"You're viewing {names[owner]}'s cycle, read-only.")
    prediction_card("partner-prediction", [c.length for c in cycles], last, today, mode_toggle())
    with card("partner-trends"):
        eyebrow("Cycle Trends")
        fig = charts.cycle_length_chart(irregularity.assess_cycles(cycles), show_flags=False)
        if fig is None:
            empty_state(icon="📈", title="No completed cycles yet", body="Their chart appears once a cycle is complete.")
        else:
            st.plotly_chart(fig, use_container_width=True, key="chart_partner")


def level2_settings_card(conn, user: auth.User) -> None:
    settings = db.get_settings(conn, user.id)
    with card("cycle-settings"):
        eyebrow("Phases and personal findings")
        if settings.is_demo:
            st.caption("In the demo, these switches only last for this browser tab.")
            labels = {
                "phase_guide": "Written Phase Guide (sends your findings — labels only — to Anthropic)",
                "week_fit": "Plan my week (sends your notes for the week to Anthropic)",
            }
            for call_type, label in labels.items():
                key = DEMO_OPT_IN[call_type]
                # Widget state is dropped once the widget isn't drawn (another
                # page), so the choice is copied to a plain session key.
                st.session_state[key] = st.toggle(label, value=st.session_state.get(key, False), key=f"w_{key}")
            st.caption(week_fit.NOTICE)
            return
        with st.form("cycle_settings"):
            options = [None, *range(db.LUTEAL_DAYS_RANGE[0], db.LUTEAL_DAYS_RANGE[1] + 1)]
            luteal = st.selectbox(
                "Luteal phase length (days from ovulation to your period)", options,
                index=options.index(settings.luteal_days),
                format_func=lambda v: f"Default ({predict.LUTEAL_DAYS})" if v is None else str(v),
                help="Only change this if you know yours, e.g. from ovulation tests. It moves the "
                     "fertile-window estimate and your phases together.",
                key="setting_luteal",
            )
            contraception = st.toggle("I use hormonal contraception", value=settings.hormonal_contraception,
                                      key="setting_contraception")
            guide = st.toggle(
                "Written Phase Guide",
                value=settings.phase_guide_opt_in, key="setting_guide",
                help="Sends only phase names, strategy names and how strong the evidence is "
                     "(plus your shortest and longest cycle length) to Anthropic to write them up.",
            )
            week = st.toggle("Plan my week", value=settings.week_fit_opt_in, key="setting_week",
                             help=week_fit.NOTICE)
            st.caption(f"Plan my week: {week_fit.NOTICE}")
            if st.form_submit_button("Save"):
                db.update_settings(conn, user.id, luteal_days=luteal, hormonal_contraception=contraception,
                                   phase_guide_opt_in=guide, week_fit_opt_in=week)
                st.toast("Saved.")


def page_settings(conn, user: auth.User) -> None:
    with card("account"):
        eyebrow("Account")
        st.markdown(f"**{user.display_name}** · {user.email}")
        if st.button("Log out", key="logout"):
            auth.end_session()
            st.rerun()

    level2_settings_card(conn, user)

    if demo.is_demo(conn, user.id):
        with card("demo-settings"):
            st.caption("The demo account can't be shared, exported or deleted — it's sample data.")
        return

    with card("sharing"):
        eyebrow("Partner sharing")
        st.caption("Sharing is one-way and read-only: they see your dashboard, trends and predictions — "
                   "never your daily logs or remedies. You can stop sharing any time.")
        if st.button("Create an invite code", key="new_invite"):
            st.session_state["last_invite"] = partner.create_invite(conn, user.id).invite_code
        if code := st.session_state.get("last_invite"):
            st.success(f"Share this code: **{partner.format_code(code)}** — it works once, for 48 hours.")
        for link in partner.links_for(conn, user.id):
            if link.owner_id != user.id or link.status not in ("pending", "accepted"):
                continue
            label = (f"Shared with {auth.get_user(conn, link.viewer_id).display_name}"
                     if link.status == "accepted" else f"Unused code {partner.format_code(link.invite_code)}")
            left, right = st.columns([3, 1])
            left.markdown(label)
            if right.button("Stop sharing" if link.status == "accepted" else "Cancel", key=f"revoke_{link.id}"):
                partner.revoke(conn, user.id, link.id)
                st.rerun()
        with st.form("redeem"):
            code = st.text_input("Got a code from someone?", key="redeem_code")
            if st.form_submit_button("Use code"):
                try:
                    partner.redeem_invite(conn, user.id, code)
                    st.success("Linked — find it under “Shared with me”.")
                except partner.InviteError as exc:
                    st.error(str(exc))

    with card("doctor"):
        eyebrow("For your doctor")
        choice = st.selectbox("Period", list(export.RANGE_CHOICES),
                              index=list(export.RANGE_CHOICES).index(export.DEFAULT_RANGE), key="doctor_range")
        report = export.build_doctor_report(conn, user.id, export.RANGE_CHOICES[choice])
        c1, c2 = st.columns(2)
        c1.download_button("Download PDF", export.doctor_pdf(report), "nova-cycle-summary.pdf",
                           "application/pdf", key="dl_pdf")
        c2.download_button("Download CSV", export.doctor_csv(report), "nova-cycle-summary.csv",
                           "text/csv", key="dl_csv")
        st.caption("A cycle-level summary: no mood, lifestyle tags or remedies.")

    with card("my-data"):
        eyebrow("Your data")
        st.download_button("Download everything (ZIP)", export.export_my_data(conn, user.id),
                           "nova-my-data.zip", "application/zip", key="dl_zip")
        with st.expander("Delete all my data"):
            st.markdown("This permanently deletes your logs, cycles, remedies, sharing links and your account. "
                        "It can't be undone.")
            confirm = st.text_input("Type your email to confirm", key="delete_confirm")
            if st.button("Delete everything", key="delete_account"):
                try:
                    db.delete_account(conn, user.id, confirm)
                except ValueError as exc:
                    st.error(str(exc))
                else:
                    auth.end_session()
                    st.session_state["deleted"] = True
                    st.rerun()


# --- main -----------------------------------------------------------------------

def main() -> None:
    st.set_page_config(page_title="Nova", page_icon="🌙", layout="centered")
    apply_theme()
    conn = db.connect(DB_PATH)
    try:
        user = auth.current_user()
        if user is not None and auth.get_user(conn, user.id) is None:
            auth.end_session()  # account deleted elsewhere
            user = None
        today = date.today()
        if user is None:
            if st.session_state.pop("deleted", False):
                st.success("Your data and account have been deleted. Take care. 🌷")
            page_login(conn)
        else:
            with st.sidebar:
                st.markdown("### 🌙 Nova")
                page = st.radio("Pages", PAGES, key="nav", label_visibility="collapsed")
            if demo.is_demo(conn, user.id):
                with card("demo-banner", tone="lavender"):
                    st.markdown(f"**{demo.BANNER}**")
            {
                "Today": lambda: page_today(conn, user, today),
                "Home": lambda: page_home(conn, user, today),
                "My phases": lambda: page_phases(conn, user, today),
                "Plan my week": lambda: page_week(conn, user, today),
                "Cycle Trends": lambda: page_trends(conn, user),
                "Insights": lambda: page_insights(conn, user),
                "Did You Know?": page_qna,
                "Shared with me": lambda: page_shared(conn, user, today),
                "Settings": lambda: page_settings(conn, user),
            }[page]()
        footer()
    finally:
        conn.close()


main()
