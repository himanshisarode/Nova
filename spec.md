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

## Data
- `users`: id, email (unique), password_hash, display_name, created_at
- `partner_links`: id, user_id (the inviter, whose data is shared),
  partner_user_id (the invitee/viewer; null until the code is redeemed),
  invite_code (unique), status (pending/accepted/revoked/expired),
  created_at, expires_at (created_at + 48h), accepted_at, revoked_at
- `daily_log`: user_id, date, + the daily fields from Feature 1 (exact
  columns: see Open Questions). Primary key is (user_id, date).
- `daily_symptom`: user_id, date, symptom — one row per symptom logged on
  a day, (user_id, date) referencing daily_log. Primary key is
  (user_id, date, symptom).
- `cycle`: user_id + cycle fields, derived from daily_log (derivation
  rule: see Open Questions)
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
2. Period prediction — Simple and Honest modes, interval-based, per user
3. Fertile window / ovulation estimate (clearly labeled as an estimate,
   not contraception)
4. Cycle Trends dashboard (per-user, styled per Design above)
5. Irregularity detection with SHAP explanations (per-user)
6. Doctor-shareable export, CSV/PDF (per-user)
7. Export-my-data / delete-all-my-data (per-user)
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
    Function contract is pinned by tests/test_lifestyle_link.py.
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
    tests/test_remedy.py.

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
- [ ] `pytest tests/` passes

## Output Files
app.py, theme.py (loads the custom CSS + card/empty-state helpers shared
by every page), db.py, auth.py, partner.py, predict.py, irregularity.py,
simulate.py, charts.py, export.py, qna_content.py (the 10 Q&A pairs as
static data, kept separate from display logic so the content is easy to
review on its own), lifestyle_link.py, remedy.py, .streamlit/config.toml,
assets/ (custom CSS), static/fonts/ (self-hosted Quicksand + its OFL
license), tests/test_db.py, tests/test_auth.py, tests/test_partner.py,
tests/test_predict.py, tests/test_simulate.py, tests/test_qna.py,
tests/test_lifestyle_link.py, tests/test_remedy.py, requirements.txt,
Dockerfile, docker-compose.yml, README.md

## Open Questions (unresolved, flagging rather than guessing)
- Exact pastel hex values given above are a starting point, not final —
  expect to adjust once the UI is actually on screen.
- Should a revoked partner's historical read access leave any trace (e.g.
  "partner had access from X to Y" in your own settings page), or just
  silently disappear? Leaning toward keeping that trace — mainly for your
  own clarity — but not firmly decided. (The schema keeps accepted_at /
  revoked_at either way, so this is only a display decision.)
- Since nothing is carried over from v1, the following used to be defined
  by "(v1)" references and now need to be written down here before the
  phase that needs them (Phase 2/3/7):
  - daily_log columns: flow levels, mood scale, the fixed symptom list,
    how lifestyle tags are stored
  - the rule for deriving a cycle (what counts as a period start)
  - Simple vs Honest prediction: what each mode computes, minimum cycles
    before predicting, interval level
  - fertile window / ovulation estimate rule
  - irregularity: what "irregular" means for labelling, which model,
    which features SHAP explains
  - export contents (which fields go in the CSV/PDF)
  - "v1's acceptance criteria still apply" — those criteria aren't in
    this file; the ones that still matter need restating here (Plan
    already has the 90% interval coverage / 0.80 recall numbers)

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
