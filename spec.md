# SPEC.md — Nova (v2)

Renamed from Interval. Same core idea (honest predictions, not fake-precise
ones), now a bigger, more complete project: accounts, partner sharing,
two local-statistics features, and a real visual design pass. Pregnancy
mode, the Symptom Checker, and Explain My Trend were scoped for v2 but are
deferred — see "Not yet built" at the bottom.
This supersedes the old Interval SPEC.md and Interval_PLAN.md — don't build
off those anymore, they're stale as of this version.

v2 is built entirely fresh in `nnova/` — no code is reused from any
earlier version. Where this spec says "(v1)" it describes where a feature
came from, not code to copy. Anything a "(v1)" feature needs that this
file doesn't define yet is listed under Open Questions, not assumed.

## Goal
A cycle-tracking app, usable by one person and, optionally, a partner they
invite — still built around explainable, statistically honest predictions
(prediction intervals, SHAP-explained flags) instead of black-box ones.

## Non-Goals (updated — some of v1's non-goals have flipped to goals below)
- Community/social chat — still cut. No group features, no public feed.
- Any multi-turn AI conversation, or an AI that decides what to do on its
  own. Both AI features are deferred (see "Not yet built"); if they come
  back, they stay single request, single reply. Never a back-and-forth,
  never autonomous.
- A full clinical-grade symptom checker — when the deferred Symptom
  Checker is built, it stays scoped as described in "Not yet built".
- Open public signup for strangers — accounts exist so you and a partner
  you specifically invite can use this together, not an arbitrary
  multi-tenant product.
- HIPAA-grade compliance or any clinical certification — this is a course
  project. Disclaimers say so, clearly, throughout the app.
- A growing, expert-reviewed content library — the "Did You Know?" Q&A
  below is a fixed ten items, written once, no video, not labeled
  "expert-reviewed" since no clinician reviewed it. If this ever grows
  past ten items or starts claiming clinical review, that's a real scope
  change, come back and amend this spec first.
- Persistent login across browser/tab restarts — a login lasts while the
  tab is open; closing it means logging in again.

## Architecture
- Streamlit, still — real custom theming (below) gets this looking
  polished without the cost of standing up a separate frontend. Flagging
  this as a deliberate call: a separate React frontend would look
  marginally more "production," but isn't worth the time against a
  two-week build, and Streamlit's theming genuinely covers what's being
  asked for here.
- SQLite, now properly multi-user — every data table carries a user_id,
  and a separate users table holds bcrypt-hashed passwords (never
  plaintext, this is non-negotiable even though we're not being paranoid
  elsewhere).
- Session handling: the logged-in user lives in Streamlit session state
  for the life of the browser tab. No cookies, no remember-me tokens.
- Partner sharing via invite code: one user (the inviter) generates a
  code, another (the invitee) enters it to link. Each link is one-way:
  the invitee becomes a read-only viewer of the inviter's data; two
  people who want mutual visibility make two links. Partner access is
  read-only, and that's enforced in the database query layer, not just
  hidden in the UI — this is a data-integrity requirement (your partner
  shouldn't be able to silently edit your logs), not a privacy add-on, so
  it's not something "don't worry about privacy much" relaxes.
- No external API calls in the current scope. Both AI features (and their
  files, explain.py and symptom_checker.py) are deferred; nothing in the
  built app sends data anywhere.
- Lifestyle-Link Finder and Remedy Effectiveness (both new, see Features)
  are deliberately NOT API calls — both are "did this actually help / is
  this actually linked" claims, which is a statistics question, not a
  language question. Routing either through an AI would mean the AI
  guessing at a pattern with no real computation behind it, which breaks
  the one rule that's held since v1: every result traces back to an
  actual statistic, never "the model said so." Both are plain
  pandas/scipy comparisons on data already being logged.
- pandas/numpy/scipy/scikit-learn/shap/plotly.

## Design ("make it look very good")
- Palette: blush pink primary (~#F6C6CE), soft lavender accent
  (~#D9C9E8), warm cream background (~#FFF8F3), charcoal text — pinned
  down now so this isn't a vague instruction Claude Code has to guess at;
  adjust once it's actually on screen and something looks off.
- Base palette via .streamlit/config.toml, further custom CSS for rounded
  cards, soft drop shadows, generous whitespace — no raw unstyled
  Streamlit widget walls.
- Rounded, friendly typography: Quicksand (a Google Font, SIL Open Font
  License), self-hosted from static/fonts/ instead of loaded from Google's
  servers at runtime, so the app makes no third-party request and works
  offline/in Docker.
- Consistent card-based layout on every page: stats, charts, and each
  feature live in their own soft-edged card.
- Feel: a cozy journal, not a hospital app. Rounded corners everywhere,
  soft shadows instead of hard borders, generous whitespace, nothing
  clinical-white-and-blue. Empty states ("not enough data yet") use warm,
  encouraging microcopy — they explain that the app is waiting for more
  data, never read as an error or a cold refusal.

## Medical disclaimer (cross-cutting — applies to the whole app)
Not tied to any one feature, deferred or built. The exact text, verbatim:

> Nova's predictions, trend charts, and irregularity flags are based on
> statistical patterns in your own logged data. This is general
> information, not medical advice, and not a diagnosis. Cycle length,
> ovulation timing, and what counts as 'irregular' can be affected by
> many things this app doesn't know about. If something feels wrong,
> changes suddenly, or worries you, please talk to a doctor or
> gynecologist - don't rely on this app alone.

- Defined once in code (theme.py) and rendered from there, never
  retyped per page.
- Must actually render in the UI — not only in docs or a settings page:
  - in the same card as every period prediction (Simple and Honest) and
    fertile-window/ovulation estimate
  - in the same card as every irregularity flag
  - in a footer on every page
  - including the partner's read-only view, which shows predictions
- Styled to match the Design section (soft, readable, not an alarming
  red box), but never collapsed or hidden behind a click.

## Data
- `users`: id, email (unique), password_hash, display_name, created_at
- `partner_links`: id, user_id (the inviter, whose data is shared),
  partner_user_id (the invitee/viewer; null until the code is redeemed),
  invite_code (unique), status (pending/accepted/revoked/expired),
  created_at, expires_at (created_at + 48h), accepted_at, revoked_at
- `daily_log`: user_id, date, flow (none/spotting/light/medium/heavy, or
  not recorded), mood (1–5, optional), poor_sleep, high_stress, travel
  (each yes/no). Primary key is (user_id, date). Any past day can be
  logged; logging a date again replaces that day's entry entirely.
- `daily_symptom`: user_id, date, symptom — one row per symptom logged on
  a day, (user_id, date) referencing daily_log. Primary key is
  (user_id, date, symptom). Fixed symptom list: cramps, headache,
  bloating, fatigue, acne, breast_tenderness, back_pain, nausea,
  mood_swings, insomnia.
- `cycle`: user_id, start_date, end_date, length — derived from
  daily_log, rebuilt on every write so it never goes stale.
  - A bleeding day is one with light, medium, or heavy flow. Spotting is
    logged but never counts as bleeding.
  - Period rule (the single rule — there is no other gap threshold):
    bleeding days separated by 6 or fewer non-bleeding days belong to
    the same period. A bleeding day starts a new period only if the 7
    days before it were all non-bleeding (unlogged, no flow, or
    spotting). So a period that pauses mid-way — e.g. bleeding day 1,
    nothing days 2–3, light flow day 4 — is still one period. A side
    effect: no cycle can be shorter than 8 days.
  - A cycle runs from one period start to the day before the next. The
    current, unfinished cycle isn't a completed cycle and isn't stored.
- `remedy_log`: id, user_id, date, symptom, remedy (free text or picked
  from past entries), relief_rating (1–5) — optional, logged alongside a
  symptom on the daily form. Remedy text is normalized before storage and
  comparison: lowercased, surrounding whitespace stripped, spaces turned
  into underscores (so "Heat Pad" and "heat_pad" are the same remedy).

## Features
Numbering is kept stable so references elsewhere don't shift; deferred
items stay listed here as a pointer.

1. Daily logging form — flow, symptoms, mood, optional lifestyle tags,
   per user
2. Period prediction — Simple and Honest modes, per user. Both use the
   most recent (up to 12) completed cycles, all of them, irregular ones
   included, and need at least 3 completed cycles; below that, a warm
   "not enough data yet" with progress — never a default like 28 days.
   - Simple: one date — last period start + mean cycle length (rounded
     half up).
   - Honest: a date range — a 90% prediction interval for the next
     cycle's length, mean ± t(0.95, n−1) · sd · √(1 + 1/n), rounded
     outward to whole days and never narrower than ±1 day.
   - Once today is past the predicted date/range, show a gentle "later
     than your usual range" message instead of a stale prediction.
3. Fertile window / ovulation estimate (clearly labeled as an estimate,
   not contraception): ovulation = predicted next start − 14 days;
   window = 5 days before ovulation to 1 day after. In Honest mode it
   spans the earliest to latest ovulation the range allows. Same
   3-cycle minimum.
4. Cycle Trends dashboard (per-user, styled per Design above)
5. Irregularity detection with SHAP explanations (per-user)
   - Flag (a transparent rule): a completed cycle is irregular if it's
     outside 24–38 days (FIGO 2018 normal frequency), or more than 7
     days from the median of the user's previous cycles (needs ≥ 3
     earlier cycles; uses up to the last 12). Each flag says why in
     plain words, e.g. "41 days — 12 days longer than your usual 29".
   - Explanation: a per-user random forest on per-cycle factors (share
     of non-bleeding days with each lifestyle tag, average mood, share
     of days with symptoms — bleeding days excluded so cycle length
     can't masquerade as a factor), explained with SHAP. Only shown
     with ≥ 3 flagged and ≥ 3 unflagged cycles, and a factor is only
     named if flagged and unflagged cycles also differ on it
     significantly (permutation test, α = 0.05 Bonferroni-split across
     the factors). Worded as an association, never a cause.
6. Doctor-shareable export, CSV/PDF (per-user). A cycle-level summary,
   not a diary. Range: last 3/6/12 months (default 12) or all time,
   by cycle start; irregularity is still judged against full history.
   - PDF: display name, date range, generated date; summary (cycle
     count, average/median, shortest/longest, typical period length,
     irregular count, current Honest prediction — or, once overdue,
     "was expected between … ; none logged as of …"); cycle-length bar
     chart (irregular in lavender); per-cycle table (start, length,
     period days, heaviest flow, irregular + reason); symptom share
     (cycles with each symptom logged at least once); the medical
     disclaimer in every page's footer.
   - CSV: the same per-cycle table (symptoms as `cramps:3; fatigue:2`).
   - Left out: email, mood, lifestyle tags, remedy log, SHAP
     explanations, partner details.
   - The irregularity reason says what happened ("12 days longer than
     your usual 29", "shorter than the 24–38 day range…"), never why —
     nothing implying a cause such as stress or sleep, since those
     factors are deliberately excluded from this export.
7. Export-my-data / delete-all-my-data (per-user)
   - Export: a ZIP of account.json (email, display name, created date),
     daily_log.csv (every field), cycles.csv, partner_links.csv (role,
     other person's display name, status, dates) — never the password
     hash or invite codes — plus remedy_log.csv.
   - Delete: one action removes everything — logs, symptoms, cycles,
     partner links in both directions, and the account. The user must
     type their account email to confirm (checked in db.delete_account,
     not just the UI), then is logged out. SQLite's secure_delete is on,
     so deleted rows are overwritten in the file, not left in free pages.
8. *Explain My Trend — deferred, see "Not yet built"*
9. Account creation + login — email + password, bcrypt-hashed; login
   lasts while the tab is open. Emails are stored lowercased and are
   unique regardless of case. Passwords need at least 8 characters and
   at most 72 bytes (bcrypt's limit — longer ones are refused, not
   silently truncated). A display name is required. A failed login says
   the same thing whether the email or the password was wrong.
10. Partner sharing — the inviter generates an invite code; the invitee
    enters it to link. Codes are single-use and expire 48 hours after
    creation if unused. The link is one-way: the invitee gets a read-only
    view of the inviter's dashboard, Cycle Trends, and predictions only —
    NOT raw daily logs, NOT the remedy log. Revocable anytime from
    settings, and revoking removes access immediately.
    - Codes are 8 characters from an alphabet without look-alikes
      (no 0/O, 1/I/L), shown as ABCD-EFGH; typing them with spaces,
      dashes, or lowercase still works.
    - Only the owner (inviter) can revoke a link or cancel an unused
      code. Revoked and expired links keep their dates in the database.
    - Concretely, the partner gets: completed cycles (for the dashboard
      and Cycle Trends), the last period start, and the Simple/Honest
      period predictions. Not the fertile-window estimate, not
      irregularity flags or their explanations (those are built from
      daily logs) — see Open Questions.
    - Enforcement: the partner reads through a separate SQLite
      connection opened read-only (mode=ro + query_only), and the link
      is re-checked on every read.
11. *Pregnancy mode — deferred, see "Not yet built"*
12. *Symptom Checker — deferred, see "Not yet built"*
13. Pastel, card-based UI throughout (see Design)
14. "Did You Know?" Q&A — a fixed page of 10 general-education questions
    and answers, written once (not AI-generated, not user-editable),
    covering common misconceptions: cycle-length "normal" range isn't
    exactly 28 days; pregnancy during a period is possible though less
    likely; ovulation isn't always day 14; mittelschmerz (ovulation
    twinges) is normal; hormonal birth control suppresses the natural
    cycle this app predicts, so predictions won't be meaningful on it;
    period blood color alone usually isn't meaningful; stress/travel/
    illness can delay a period; PCOS and endometriosis are common and
    often diagnosed late; "heavy flow" alone isn't automatically
    abnormal; fertility decline with age is gradual, not a cutoff. Each
    answer is a short paragraph, clearly labeled as general education,
    not personalized medical advice, with the same "talk to a doctor if
    this sounds like you" framing used elsewhere in the app.
15. Lifestyle-Link Finder — for each lifestyle tag being logged (poor
    sleep, high stress, travel), splits your cycles into "tag present" vs
    "tag absent" and compares average cycle length between the two
    groups. A cycle counts as "tag present" if the tag was logged on any
    day within it. The test is a two-sided Welch's t-test at alpha=0.05.
    Needs at least 3 cycles in each group before showing anything; below
    that, "not enough data yet" — same discipline as the period
    predictor. Result is a plain sentence: either a real, statistically
    significant link ("cycles with high stress logged ran 2.3 days longer
    on average"), or an honest "no significant link found yet" if the
    pattern doesn't hold up. Pure local computation, zero API calls.
    Function contract is pinned by tests/test_lifestyle_link.py. If both
    groups have no spread at all (every cycle the same length), the
    t-test is undefined and the result is "no significant link".
16. Remedy Effectiveness Tracker — when logging a symptom, optionally
    also log what you tried for it and a 1–5 relief rating
    (`remedy_log`, remedy text normalized as in Data). Once a (symptom,
    remedy) pair has at least 3 logged instances, the app shows its
    average relief rating and the pair is "ranked" — even if it's the
    only remedy for that symptom with enough data. Pairs below that
    threshold are shown as "not enough data yet" rather than a
    misleadingly confident number. Ranked remedies for the same symptom
    are ordered by average rating, highest first. Pure local computation
    (average + count), zero API calls. Function contract is pinned by
    tests/test_remedy.py. Normalizing also collapses runs of whitespace
    into one underscore ("Heat   Pad" → heat_pad). Pairs without enough
    data carry no average at all, and are listed after ranked ones.

## Acceptance Criteria
- [ ] Two accounts can be created and linked via invite code; the invited
      partner sees a read-only view and cannot edit the other account's
      logs (tested at the query layer, not just the UI)
- [ ] The partner view exposes dashboard, Cycle Trends, and predictions
      only — partner-scoped queries cannot return raw daily logs or the
      remedy log (tested)
- [ ] Invite codes are single-use (a second redemption fails) and expire
      48 hours after creation (an expired code fails) — tested
- [ ] Links are one-way: linking A→B gives B read access to A, not A to B
      — tested
- [ ] Revoking a partner link removes access immediately — tested, not
      assumed
- [ ] No plaintext password ever appears in the database file (grep the
      raw file in a test and assert the known test password string isn't
      present)
- [ ] `docker compose up` still serves the app with no errors, and data
      for multiple users survives a full container restart
- [ ] All 10 "Did You Know?" entries render with a non-empty question and
      answer, and the page never calls any API — static content only
- [ ] Lifestyle-Link Finder shows "not enough data yet" below 3 cycles
      per group, and a correctly-computed significance result above that
      threshold — validated against a hand-built synthetic example with
      a known, deliberately planted link (tests/test_lifestyle_link.py,
      fixed, not to be rewritten)
- [ ] Remedy Effectiveness shows "not enough data yet" below 3 logged
      instances for a given (symptom, remedy) pair, and a correct average
      above that threshold (tests/test_remedy.py, fixed, not to be
      rewritten); differently-typed spellings of the same remedy ("Heat
      Pad" / "heat_pad") are counted together
- [ ] Neither Lifestyle-Link Finder nor Remedy Effectiveness ever makes a
      network call — tested the same way the Q&A page is
- [ ] The medical disclaimer genuinely renders in the app, not just in
      the docs: a UI test (Streamlit AppTest) runs every page that shows
      a prediction, fertile-window estimate, or irregularity flag —
      including the partner view — and asserts the exact disclaimer
      text is present in the same card as each of them, and in the
      footer of every page
- [ ] The disclaimer text in code matches the text in this spec word for
      word (a test reads spec.md and compares, ignoring line wrapping),
      so the two can't drift apart
- [ ] Honest prediction: on simulated people with 15% irregular cycles,
      the shown date range contains the actual next period start 85–95%
      of the time; on clean simulated data the unrounded interval is
      calibrated (88–93% for a nominal 90%)
- [ ] Irregularity: on simulated people, at least 80% of planted
      irregular cycles are flagged, and at most 10% of normal cycles
- [ ] Irregularity explanations find a planted factor (≥ 80% of
      simulated people with a planted stress link) and stay quiet
      without one (≤ 15% of simulated people with no planted pattern
      get any explanation)
- [ ] Doctor export (CSV and PDF) contains only that user's data and
      none of the excluded details (email, mood, tags, remedy, SHAP,
      partner) — tested by searching the generated text; its
      irregularity reasons never name a cause
- [ ] After delete-all-my-data, a test reads the raw database file and
      finds none of the user's name, email, or password hash — with a
      control test showing the same search does find them when
      secure_delete is off
- [ ] The period rule's boundary is pinned by tests: bleeding day 1,
      nothing days 2–3, light flow day 4 is one period; 6 non-bleeding
      days between bleeds is still one period; 7 starts a new one
- [ ] `pytest tests/` passes

## Output Files
app.py, theme.py (loads the custom CSS + card/empty-state helpers shared
by every page), db.py, auth.py, partner.py, predict.py, irregularity.py,
simulate.py, charts.py, export.py, qna_content.py (the 10 Q&A pairs as
static data, kept separate from display logic so the content is easy to
review on its own), lifestyle_link.py, remedy.py, .streamlit/config.toml,
assets/ (custom CSS), static/fonts/ (self-hosted Quicksand + its OFL
license), tests/test_db.py, tests/test_auth.py, tests/test_partner.py,
tests/test_predict.py, tests/test_simulate.py, tests/test_irregularity.py,
tests/test_theme.py, tests/test_export.py, tests/test_charts.py, tests/test_local_stats.py, tests/test_app.py, tests/test_docker.py, tests/conftest.py (no_network fixture), tests/ui_checks.py (shared AppTest helpers for the
disclaimer checks), tests/test_qna.py,
tests/test_lifestyle_link.py, tests/test_remedy.py, requirements.txt,
Dockerfile, docker-compose.yml, .dockerignore, README.md

## Open Questions (unresolved, flagging rather than guessing)
- Exact pastel hex values given above are a starting point, not final —
  expect to adjust once the UI is actually on screen.
- Should a revoked partner's historical read access leave any trace (e.g.
  "partner had access from X to Y" in your own settings page), or just
  silently disappear? Leaning toward keeping that trace — mainly for your
  own clarity — but not firmly decided. (The schema keeps accepted_at /
  revoked_at either way, so this is only a display decision.)
- Should a partner also see the fertile-window estimate and/or
  irregularity flags? Feature 10 lists "dashboard, Cycle Trends, and
  predictions", which could include either. Built conservatively for
  now (neither shown); each is a one-method addition to PartnerView if
  wanted. The fertile window is the more sensitive of the two.
- Should a viewer be able to end a link themselves ("stop viewing")?
  Currently only the owner can revoke.
- Fertile window with varied cycles: the method (as approved) spans the
  whole Honest range, so for cycles of 20–35 days the window can cover
  ~4 weeks and start on the period's first day. That's honest, but
  nearly useless as shown. Option: above ~10 days wide, say plainly
  that the cycles vary too much to narrow it down, instead of a date
  span. Not changed yet.
- Lifestyle-Link "any day" rule (Q4): a tag logged even occasionally
  marks almost every cycle as tagged — at 2–3 stress days a month,
  roughly 9 in 10 cycles count as "high stress" — so the "without" group
  rarely reaches 3 and the feature seldom gives a result. Options: a
  cycle counts as tagged only above some share of its days, or compare
  the share of tagged days against cycle length instead of two groups.
  The fixed test file only pins check_lifestyle_link(), not how cycles
  get their tags, so either option leaves it untouched. Not changed yet.
- Since nothing is carried over from v1, the following used to be defined
  by "(v1)" references and now need to be written down here before the
  phase that needs them (Phase 7). (daily_log columns and the cycle
  rule were settled for Phase 2, prediction/fertile window/irregularity
  for Phase 3 — see Data and Features.)
  - "v1's acceptance criteria still apply" — those criteria aren't in
    this file; the ones that still matter need restating here (the
    prediction and irregularity ones now live in the acceptance list
    below Features)

## Not yet built
Deferred from v2's original scope to keep the two-week build realistic.
Described here so they're not lost; each needs its own spec pass before
it's started.

- **Explain My Trend (Feature 8)** — one AI call, sending only
  pre-computed aggregate numbers, never raw logs; single request, single
  reply. Would live in explain.py with tests/test_explain.py. Needs an AI
  provider chosen first (not decided). Note: this is a new feature, not a
  v1 carry-over.
- **Pregnancy mode (Feature 11)** — toggle from cycle-tracking to
  pregnancy-tracking; due date estimated from logged last-period start
  date, a running week counter, and a simple weekly log (weight,
  symptoms, notes) with its own trend chart. Purely administrative
  calculation and your own logged data — not medical guidance. Data:
  `pregnancy` (id, user_id, last_period_start_date, due_date (computed),
  mode_active) and `pregnancy_log` (id, pregnancy_id, date, weight,
  symptoms, notes). Would live in pregnancy.py with
  tests/test_pregnancy.py. Acceptance when built: due-date and
  week-counter numbers checked against hand-calculated examples.
  Undecided before starting: due-date convention (e.g. Naegele's rule),
  week-counter display format, what happens to cycle predictions while
  active, and how leaving the mode is handled (including pregnancy loss).
- **Symptom Checker (Feature 12)** — pick from a fixed list of 15 common,
  non-urgent symptoms: cramping, bloating, breast tenderness, fatigue,
  headache (typical/mild), mood swings, acne breakouts, lower back pain,
  nausea, food cravings, insomnia, light spotting between periods, breast
  swelling, joint/muscle aches, brain fog. One AI call (sending only the
  selected labels from the fixed list, nothing else) returns a few
  common, benign possible explanations, always followed by a hardcoded
  (not AI-generated) disclaimer that this isn't a diagnosis. Separately,
  a fixed urgent list — soaking a pad/tampon every hour for 2+ hours
  straight, sudden/severe abdominal or pelvic pain, fever (100.4°F/38°C+)
  with pelvic pain, fainting or severe dizziness, chest pain or shortness
  of breath, a sudden severe headache with vision changes, and (only when
  pregnancy mode is active) severe swelling/headache with vision changes
  or a noticeable drop in movement — shows a hardcoded "seek medical care
  now" message instead, and never calls the AI. Would live in
  symptom_checker.py with tests/test_symptom_checker.py. Acceptance when
  built: outgoing request body asserted to contain only fixed-list labels;
  urgent selections make zero AI calls (tested). Undecided before
  starting: AI provider; reconciling its symptom names ("cramping") with
  the daily log's vocabulary; the lists need clinician review if ever
  used beyond a demo.
