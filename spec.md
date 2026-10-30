# SPEC.md — Nova (v2)

Renamed from Interval. Same core idea (honest predictions, not fake-precise
ones), now a bigger, more complete project: accounts, partner sharing,
two local-statistics features, and a real visual design pass. Pregnancy
mode and the Symptom Checker were scoped for v2 but are deferred — see
"Not yet built". Explain My Trend was dropped; the LLM layer replaces it.
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

Level 2 scope (branch `level2`, Features 17–23): Nova also becomes a
personal cycle-syncing tool. Nothing in it gives generic "days 1–5 do
yoga" advice: phases come from the user's own cycles, and what tends to
go well in each phase is learned from the user's own "what works for me"
log, then (optionally) written up and fitted around her week by exactly
two kinds of LLM call (see "LLM layer (Level 2)"). The app stays
English-only. Every choice made for this scope, with its alternatives,
is explained in plain language in DECISIONS.md.

## Non-Goals (updated — some of v1's non-goals have flipped to goals below)
- Community/social chat — still cut. No group features, no public feed.
- Any multi-turn AI conversation, or an AI that decides what to do on its
  own. The LLM layer's two call types (see "LLM layer (Level 2)") are
  single request, single reply; so is the deferred Symptom Checker if it
  comes back. Never a back-and-forth, never autonomous.
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
- External API calls: only through llm.py, only the two call types in
  "LLM layer (Level 2)", only after the user opts in, and only with the
  payloads listed under "Constraints". Everything else in the app, the
  new by-phase analysis included, is local computation. Without an API
  key the app is fully usable: both LLM features show their template
  versions. The Symptom Checker (symptom_checker.py) stays deferred.
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

Level 2 additions. All additive: new nullable columns and new tables, no
existing column changed or dropped, applied by db.migrate() at startup
(see "Migration").
- `daily_log` gains `day_rating` ("how did today go", 1–5, nullable) and
  `energy` (1–5, nullable).
- `daily_strategy`: user_id, date, strategy — one row per strategy tried
  that day, (user_id, date) referencing daily_log, primary key
  (user_id, date, strategy). Fixed list of 10 (STRATEGIES in db.py):
  walk, yoga, strength, cardio, rest_day, deep_focus_work, light_admin,
  social_plans, early_night, journaling. This is a separate table, not
  an extension of `remedy_log`: a remedy answers "what eased this
  symptom" (it needs a symptom and a relief rating), a strategy answers
  "what did I do today" and is judged against the day's rating. Feature
  16 is untouched. No calorie, weight, food or diet-restriction item, now
  or later.
- `user_settings`: user_id (primary key), luteal_days (10–17, null =
  default 14), hormonal_contraception (0/1, null = not answered, treated
  as no), phase_guide_opt_in (0/1, null = off), week_fit_opt_in (0/1,
  null = off), is_demo (0/1, null = no).
- `phase_guide`: user_id, cycle_start (the newest completed cycle's
  start; primary key with user_id), guide_json, created_at. Only LLM
  output that passed validation is stored; templates are recomputed.
- `llm_usage`: user_id, day, call_type, count — primary key (user_id,
  day, call_type). Enforces the daily caps server-side.
- Week Fit notes and generated weeks are never stored anywhere.

Migration: db.migrate() runs on every connect, checks PRAGMA table_info
and adds only what is missing (ALTER TABLE ... ADD COLUMN, CREATE TABLE
IF NOT EXISTS). It never rewrites, deletes or copies rows. It is tested
on a database built by the pre-Level-2 schema: every pre-existing row is
byte-identical afterwards.

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
   not contraception): ovulation = predicted next start − L days, where
   L is the user's luteal_days setting (10–17, default 14 — decision (a),
   DECISIONS.md); window = 5 days before ovulation to 1 day after. In Honest mode it
   spans the earliest to latest ovulation the range allows. Same
   3-cycle minimum. If recent cycles (the last ≤ 12) vary by more than
   9 days shortest-to-longest (the lenient end of FIGO 2018's 7–9 day
   regular spread), no window is shown — it would cover most of the
   cycle — and the card instead gently suggests talking to a doctor or
   gynecologist, saying how much the cycles have varied.
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
     explanations, partner details — and all Level 2 data: day rating,
     energy, strategies, phase labels, settings, Phase Guide, LLM usage.
   - The irregularity reason says what happened ("12 days longer than
     your usual 29", "shorter than the 24–38 day range…"), never why —
     nothing implying a cause such as stress or sleep, since those
     factors are deliberately excluded from this export.
7. Export-my-data / delete-all-my-data (per-user)
   - Export: a ZIP of account.json (email, display name, created date),
     daily_log.csv (every field), cycles.csv, partner_links.csv (role,
     other person's display name, status, dates) — never the password
     hash or invite codes — plus remedy_log.csv, and for Level 2:
     what_works_log.csv (date, day_rating, energy, strategies),
     settings.json, phase_guide.csv, llm_usage.csv.
   - Delete: one action removes everything — logs, symptoms, cycles,
     partner links in both directions, Level 2 data (strategies,
     settings, stored Phase Guides, LLM usage counts), and the account. The user must
     type their account email to confirm (checked in db.delete_account,
     not just the UI), then is logged out. SQLite's secure_delete is on,
     so deleted rows are overwritten in the file, not left in free pages.
8. *Explain My Trend — dropped; replaced by the LLM layer (one sentence
   in Phase Guide, see "LLM layer (Level 2)")*
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
    - Level 2 data is invisible to a partner: PartnerView's public API
      does not change (its pinning test stays as is), so phases,
      ratings, strategies, findings, Phase Guide and settings are
      unreachable from it.
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

Level 2 (Features 17–23). Appendix A is the reference for everything
that names a phase; the decisions it asks for are recorded in
DECISIONS.md (a)–(d) and applied below.

17. Personal phase tracker (phases.py) — phases come from the user's
    own cycles, never a 28-day template, and are always labelled as
    estimates with windows, not single days. L = luteal_days setting.
    - Completed cycles (start S, next start N): period days = S through
      the last bleeding day of that period (the Data section's period
      rule); ovulation estimate = N − L, counted backwards from the next
      period start (Appendix A3); ovulation window = N − L − 2 to
      N − L + 2; luteal = the days after the window up to N − 1;
      follicular = everything between the period and the window. Where
      a short cycle makes these overlap, period wins, then luteal.
    - Current cycle: period days from the log; the rest uses the Honest
      prediction (Feature 2) of the next start, E..T: ovulation window =
      E − L − 2 to T − L + 2, luteal estimate from T − L + 3. Shown with
      that uncertainty, not hidden. Below 3 completed cycles, only the
      period is shown ("not enough cycles to estimate the rest yet").
      Once the period is late (Feature 2), the phase reads "luteal or a
      new period — not sure" instead of a stale guess.
    - Display uses the four familiar names (period, follicular,
      ovulation window, luteal). The analysis uses 3 buckets —
      decision (b): period / follicular (rest of follicular plus the
      ovulation window) / luteal.
    - It builds on Feature 3: same L, same Honest prediction; the
      fertile window is not re-implemented.
    - Not shown on the daily logging screen (decision (c)): the Today
      page never names a phase, to avoid nudging the day's rating.
    - Hormonal contraception (decision (d)): the tracker stays, under a
      caveat that hormonal contraception usually means there's no
      natural cycle for these phases to describe.
18. "What works for me" log — optional, on the Today form, under the
    existing fields: tick strategies tried today from the fixed list of
    10 (Data), one "how did today go" rating (1–5) and an optional
    energy rating (1–5). One tap per item, no typing, so it takes well
    under 20 seconds. No calorie, weight or diet tracking or content.
19. The 6-month gate (gate.py) — the personalised features (Feature 20's
    findings, Phase Guide, Week Fit) appear only when ALL of:
    - the first logged day is at least 180 days before today;
    - at least 4 completed cycles (not 6: with 35–38 day cycles, 180
      days holds only 4 completed cycles, so 6 would lock out users
      with long but normal cycles for 7–8 months);
    - at least 50% of the last 180 days have a log entry (90 days).
    Before the gate: a warm progress view (three progress bars, one per
    condition, "x of y so far") and the phase tracker; no findings, no
    plan, no LLM call. Users on hormonal contraception never pass to
    the plan (decision (d)); they see the caveat instead.
20. "What works for me, by phase" (whatworks.py) — local statistics.
    - Data: rated days (day_rating present) in completed cycles only,
      each placed in one of the 3 buckets by Feature 17. The current
      cycle is excluded (its phases are forward guesses).
    - For each (bucket, strategy): compare the day rating on days the
      strategy was used against days it wasn't, within the same cycle
      and the same bucket — the user's own baseline for that phase.
    - Minimum before any result: 8 uses in that bucket, spread over at
      least 4 different cycles that each also have at least one rated
      non-use day in that bucket. Below that: "not enough data yet"
      with the counts, never a number.
    - Method (days within a cycle aren't independent): a stratified
      permutation test. Statistic: the weighted mean over cycles of
      (mean rating on use days − mean on non-use days), weight
      n_use·n_non/(n_use+n_non). Null distribution: shuffle which days
      were "use" days within each cycle separately, keeping each
      cycle's number of use days. Exact enumeration when there are at
      most 20,000 arrangements, otherwise 5,000 random shuffles with a
      fixed seed (p = (1 + hits)/(1 + 5,000)). Two-sided.
    - Multiple comparisons: Benjamini–Hochberg over every pair that met
      the minimum, at q < 0.10 (an addition to decision (b), explained
      in DECISIONS.md).
    - Result per pair: "tends to go well" (positive, q < 0.10), "tended
      to be rated lower" (negative, q < 0.10), or "no clear difference".
      Confidence tier for positives: "strong evidence" (q < 0.01 and
      ≥ 6 cycles), "moderate evidence" (q < 0.05), "early sign"
      (q < 0.10).
    - Wording is associative only: "In your data, days with a walk
      during your luteal phase tended to be rated higher (3.9 vs 3.1)".
      Never "because", "boosts", "your hormones". Stated limits on the
      page: strategies are chosen by feel (a good day may cause the
      walk, not the other way round); days close together still affect
      each other; phases are estimates.
    - Shown only after the gate and not for hormonal contraception.
21. Demo mode (demo.py) — a labelled demo account ("Demo (sample
    data)", email demo@nova.invalid, no usable password) seeded from
    simulate.py with 10 completed cycles (over 8 months) of logs, day
    ratings and strategies, with a planted per-phase effect (strength
    in follicular, early night in luteal, walk on period days). Entered
    with a "Try the demo" button on the login page. Every page shows a
    "Demo data — not a real person" banner. It cannot mix with real
    accounts: it can't save logs, create or redeem invite codes, and
    signup refuses the @nova.invalid domain; partner.py enforces the
    invite rules itself, not just the UI. Opt-ins for the demo live in
    the visitor's tab session only. The demo data is re-seeded when
    it's older than today (synthetic rows only). The same seeding
    function is the end-to-end test fixture.
22. Phase Guide (LLM call 1) — see "LLM layer (Level 2)". Off until the
    user opts in (Settings); without opt-in, or without a key, or on
    any failure, the template version shows.
23. Week Fit (LLM call 2) — see "LLM layer (Level 2)", "Plan my week"
    page. Off until the user opts in; the template version needs no
    opt-in because it reads no notes.

## Constraints (what leaves the machine)
Provider: Anthropic API, model `claude-opus-5-5` (one constant in
llm.py), effort low, structured JSON output. Anthropic deletes API
inputs and outputs within 30 days and does not use API data for
training by default (checked 2026-10-30, sources in DECISIONS.md).
The request goes from the Fly.io machine, so the provider sees the
server's address, never the user's. Nothing below is sent unless the
user has opted in to that call type.

| Call | Sent | Never sent |
|---|---|---|
| Phase Guide | A fixed system prompt; the 3 phase labels; for each phase the strategy labels that "tend to go well" with their confidence tier; the user's typical cycle-length range as two whole numbers (shortest–longest of the last ≤ 12 cycles) | Dates, free text, name, email, user id, symptoms, mood, ratings, log rows, counts per day |
| Week Fit | A fixed system prompt; for each of the next 7 days: the day name (e.g. "Tuesday"), its candidate phase label(s), the strategy labels offered for it with tiers, and the user's note for that day (≤ 200 characters, already passed the local email/phone check) | Dates, name, email, user id, symptoms, mood, ratings, log rows, anything about other days' notes beyond the notes themselves |

Both payloads are built by one function each (phase_guide.payload(),
week_fit.payload()) and tests assert on the real HTTP request body the
SDK would send. The API key comes only from the ANTHROPIC_API_KEY
environment variable (a Fly secret in production, never a file in the
repo). No payload, note or model output is written to logs or the
database (except a validated Phase Guide, which contains no user text).

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

Level 2 (Features 17–23; the LLM layer's own list is in its section):
- [ ] Phase tracker: on hand-worked cycles (incl. a 24-day and a 38-day
      cycle, and luteal_days 12 vs 14), every day gets the expected
      phase; ovulation for completed cycles is counted back from the
      next start; the current cycle shows a window, never one day; no
      28-day default anywhere (a user with 3+ cycles of 35 days gets
      phases scaled to 35)
- [ ] Changing luteal_days moves the fertile window (Feature 3) and the
      phases together; the default (null) behaves exactly as before
      (existing fertile-window tests unchanged)
- [ ] The Today page never shows a phase name (AppTest)
- [ ] "What works for me" fields save and reload; rating/energy outside
      1–5 and unknown strategies are refused by db.py, not just the UI
- [ ] Gate: each of the three conditions blocks on its own (boundary
      tests at 179/180 days, 3/4 cycles, 89/90 logged days); before the
      gate no finding, plan or LLM call is reachable (AppTest)
- [ ] By-phase analysis: on a hand-built fixture with expected values
      computed by hand (in the test's comments), the planted effect is
      found with the exact statistic and exact p-value, the no-effect
      negative control is not, and pairs below 8 uses / 4 cycles return
      "not enough data"; tests/test_whatworks_fixture.py is fixed once
      written, like test_lifestyle_link.py
- [ ] By-phase analysis on simulated people: planted effects found in
      ≥ 80% of people, and ≤ 10% of people with no planted effect get
      any "tends to go well" finding
- [ ] Hormonal contraception: findings, Phase Guide and Week Fit are off
      and the caveat shows (AppTest)
- [ ] Demo: seeded with ≥ 8 months, the planted effects are found end
      to end; the demo can't save logs or create/redeem invites
      (function level); signup refuses @nova.invalid; the banner shows
      on every page
- [ ] Level 2 data is absent from the doctor export (CSV and PDF text)
      and unreachable from PartnerView; present in the full export;
      gone after delete-all (raw-file grep)
- [ ] Migration: a database created with the pre-Level-2 schema and
      data opens with the new code, gains the new columns/tables, and
      every pre-existing row is unchanged (also run on a copy of the
      local data/nova.db)
- [ ] No test makes a real provider call (the no_network fixture guards
      every LLM test; the provider is mocked at the HTTP transport)

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

Level 2 adds: phases.py, gate.py, whatworks.py, demo.py, llm.py,
wording.py (output checks shared by both LLM calls), phase_guide.py,
week_fit.py, DECISIONS.md, scripts/check_migration.py,
scripts/eval_week_fit.py + eval/week_fit_samples.json (stretch),
tests/test_phases.py, tests/test_gate.py, tests/test_level2_db.py,
tests/test_whatworks.py, tests/test_whatworks_fixture.py (fixed once
written), tests/test_demo.py, tests/test_llm.py,
tests/test_phase_guide.py, tests/test_week_fit.py,
tests/test_migration.py, tests/test_level2_app.py.

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
- Lifestyle-Link "any day" rule (Q4): a tag logged even occasionally
  marks almost every cycle as tagged — at 2–3 stress days a month,
  roughly 9 in 10 cycles count as "high stress" — so the "without" group
  rarely reaches 3 and the feature seldom gives a result. Options: a
  cycle counts as tagged only above some share of its days, or compare
  the share of tagged days against cycle length instead of two groups.
  The fixed test file only pins check_lifestyle_link(), not how cycles
  get their tags, so either option leaves it untouched. Parked by
  decision (2026-10-27): left as-is for now, revisit later.
- Since nothing is carried over from v1, the following used to be defined
  by "(v1)" references and now need to be written down here before the
  phase that needs them (Phase 7). (daily_log columns and the cycle
  rule were settled for Phase 2, prediction/fertile window/irregularity
  for Phase 3 — see Data and Features.)
  - "v1's acceptance criteria still apply" — those criteria aren't in
    this file; the ones that still matter need restating here (the
    prediction and irregularity ones now live in the acceptance list
    below Features)

- Level 2 ambiguities, flagged rather than guessed (each is resolved in
  DECISIONS.md, and each could be revisited):
  - The LLM layer's table says Phase Guide needs no opt-in; the
    Level 2 rules say both LLM features are off until the user opts
    in. The stricter rule wins: Phase Guide is opt-in too.
  - Appendix A mentions a "Phase Planner"; read as the two LLM
    features plus Feature 20 (there is no separate planner).
  - "Personalised plan" in decision (d) is read as Feature 20's
    findings plus Phase Guide; the phase tracker itself stays.
  - seasons.py (design preview, not wired in) maps 4 phases to 4
    seasons; the analysis uses 3 buckets. Display names stay 4.
  - The demo account is shared by every visitor of the hosted app, so
    it is read-only for logs, and its LLM caps are shared too.

## Not yet built
Deferred from v2's original scope to keep the two-week build realistic.
Described here so they're not lost; each needs its own spec pass before
it's started.

Explain My Trend (Feature 8) is no longer here: it was dropped, not
deferred. The LLM layer (see "LLM layer (Level 2)") replaces it, and its
job is now one sentence inside Phase Guide. There is no separate
explain.py.

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

## LLM layer (Level 2)

### Why an LLM here, and only here
Statistics decide what is true about the user: predictions, phase effects,
which strategies tend to go well. The LLM is used for what a form or a
template can't do: reading an open-ended week written in the user's own words
and fitting her findings around it (Week Fit), and writing the findings up
readably (Phase Guide). It never computes, never decides which strategies the
findings support, and never sees her logs, symptoms, dates or identity.
Honest limit: Phase Guide could be a template, and its fallback is one. Week
Fit is the call that needs a language model, because the constraints in a
real week are open-ended and a template can't read them.

### What "Level 2" means here
Exactly two kinds of LLM call, each one request and one reply, each with a
hard daily limit. No multi-turn chat, no tool use, no memory between calls,
no model deciding what happens next. The app stays English-only.

### How the two calls differ
| | Phase Guide | Week Fit |
|---|---|---|
| Question | What tends to go well for me in each phase? | Given my real week, where do those things fit? |
| When | After the gate, at most once per completed cycle; result kept in the DB | On request, any time after the gate |
| User-written text | None | A short note per day, max 200 characters |
| Output | A short guide per phase | 1-2 suggestions per day, one short sentence each |
| Template fallback | Strategies per phase as a plain list | Strategies per day by that day's phase; notes not read |
| Opt-in needed | Yes (Level 2 rule: both LLM features are off until the user opts in; see Open Questions) | Yes (free text leaves the machine) |

### Call 1: Phase Guide
- Runs only after the 6-month gate.
- Local code chooses the strategies (findings that cleared the significance
  bar). The LLM only phrases them. It may add one plain-language sentence
  about the user's typical cycle length range, from numbers only.
- Payload: phase labels, strategy labels, and a confidence tier for each
  (e.g. "tends to go well, moderate evidence"). No dates, no free text, no
  identity, no raw logs.
- Output is validated: only the supplied strategies, associative wording
  ("tends to"), no medical advice. Any violation rejects the output and shows
  the template version.
- The standing medical disclaimer renders next to the guide.

### Call 2: Week Fit
- Where: a "Plan my week" page, after the gate.
- The user writes a short note for each of the next 7 days (e.g. "report due",
  "mum visiting", "early lecture"). One box per day, so the model never has to
  resolve "next Tuesday".
- Per day, local code supplies the day name (not the date), the estimated
  phase for that day, and the strategies that tend to go well in that phase,
  with confidence tiers. Phases for coming days are estimates. A day inside
  the uncertainty window gets both candidate phases, and only strategies that
  tend to go well in both are offered. Claude Code proposes the exact rule.
  Rule (decided): for each day, phases.candidate_buckets() tries every
  possible next-period start in the Honest range E..T and collects the
  bucket the day would fall in for each (a day on or after a candidate
  start counts as period for the typical period length, then
  follicular). One bucket → that bucket's strategies. Two or three →
  only strategies that tend to go well in all of them (intersection);
  if none, the day gets no suggestion and says why. Once the period is
  late, every day is {luteal, period}. Below 3 cycles there is no
  prediction and Week Fit isn't offered (the gate needs 4 anyway).
- Output, per day: 1-2 strategies chosen only from the list supplied for that
  day, plus one sentence (max 25 words) saying how they fit the day's note.
  It never reschedules, adds or removes the user's commitments, and gives no
  medical advice.
- Output is validated: strategies not in that day's list are dropped, an
  invalid structure is rejected, and either case shows the template.
  Limit, stated honestly: code can't fully verify that a sentence is faithful
  to the user's note. So each sentence is shown next to the user's own note,
  and kept short.
- Privacy: this is the one place user-written text leaves the machine. It is
  about her schedule, which is less sensitive than symptoms, but not zero.
  Opt-in per user, off by default, with a notice before first use ("what you
  type here is sent to <provider>; don't include names, contact details or
  health details"). A local check rejects text that looks like an email
  address or phone number. Revocable in settings.
- The notes and the generated week are kept only for the request and the
  current screen. They are not stored, not logged, not exported.
- Notes are untrusted text. Output is validated against the supplied lists, so
  instructions hidden inside a note can't add anything.

### Rules for both calls
- One thin module, llm.py. Swapping providers is a one-file change. The
  provider is chosen after Claude Code reports 2-3 options with current
  pricing, free-tier status, data-retention and training-on-inputs policy, and
  what it could not verify.
  Chosen: Anthropic (claude-opus-5-5, effort low). The comparison with
  Groq and Google Gemini is in DECISIONS.md.
- The API key comes from an environment variable or secret, never from code.
  .env is gitignored. pytest mocks the provider and makes no real calls.
- Per-user daily cap for each call type, stored in the database and enforced
  server-side. Proposed: Phase Guide 3/day, Week Fit 5/day. Friendly message
  when reached. Decided as proposed; every attempt counts, including
  failed ones, and the counter is taken before the request is sent
  (one transaction), so a retry loop can't exceed it. "Day" is the
  server's UTC date.
- If a call fails (no network, bad key, provider down), show a short message
  and the template version. Everything else keeps working.
- No payload or note text appears in application logs.

### Evaluation (Week Fit)
A hand-built set of about 15 sample weeks, each with day notes and the allowed
strategies. A separate script (not pytest) runs the real provider on them and
reports (a) how often the raw output passed validation without falling back
to the template, and (b) a sensible-fit rate, where I mark each day's
suggestion as respecting that day's note or not. Record both numbers in
README.md as informational, with the small-sample caveat.

### Acceptance criteria
- [ ] Exactly two call types exist, and a test confirms nothing else reaches
      llm.py
- [ ] Phase Guide payload contains only labels, tiers and numbers (test
      asserts on the real request body)
- [ ] Week Fit payload contains only day names, phase labels, strategy labels,
      tiers and the per-day notes: no dates, user id, email, name, symptoms or
      log rows
- [ ] A mocked response containing a strategy not supplied is dropped (Week
      Fit) or rejected (Phase Guide), and the template is shown
- [ ] A day note containing "ignore previous instructions..." changes nothing
      beyond the allowed output (mocked adversarial response)
- [ ] A note that looks like an email address or phone number is rejected
      locally and never sent
- [ ] After use, the database and logs contain no note text (test greps both)
- [ ] The daily cap blocks call N+1, per user and per call type
- [ ] Provider failure leaves the app usable and shows the template
- [ ] Week Fit is off until the user opts in, and revoking stops it
- [ ] No API key in tracked files
- [ ] The evaluation script runs, and its results are in README.md

### Non-goals for the LLM layer
- No chat, no follow-up questions, no tool use, no memory between calls
- No UI translation, no multi-language input
- No separate Explain My Trend call (its job is one sentence in Phase Guide)
- No Symptom Checker (still deferred)
- No calendar integration
- The LLM never infers flow, mood, energy, or the daily rating

## Appendix A — Cycle phase reference (for Claude Code)

Read this before building or changing anything that names a phase: the phase
tracker, the by-phase analysis, the Phase Planner, or any Q&A wording. It is
background, not a feature list. Where it says DECISION NEEDED, stop and ask
me. Don't pick silently. Facts are paraphrased from the linked sources, and
the sources vary in quality (noted below).

### A1. Phase basics
(Cleveland Clinic patient-education pages, see A6)
- A cycle runs from the first day of one period to the day before the next.
  Normal is roughly 21–35 days. 28 is the commonly quoted average. A period
  of 3–7 days is normal.
- Ovulation splits the cycle into two halves: follicular (starts on day 1 of
  the period, ends at ovulation) and luteal (ovulation to the next period).
- Many consumer sources show four phases: menstruation, follicular,
  ovulation, luteal. Menstruation overlaps the early follicular phase, and
  "ovulation" is a short window around one event, so the four are not four
  clean, separate blocks.
- Hormones: estrogen and progesterone are both low at the start of a period.
  Estrogen rises through the follicular phase, an LH surge triggers
  ovulation, progesterone dominates the luteal phase, and then both fall if
  there is no pregnancy, which brings the next period.
- Luteal phase: about 14 days is commonly quoted, 10–17 is called normal, and
  it stays fairly consistent within one person. Follicular phase: 14–21 days
  is quoted, and it is the half that varies.

### A2. Real-world numbers
Bull et al. 2019, npj Digital Medicine: 612,613 ovulatory cycles from 124,648
users of one app (Natural Cycles). Caveats: some authors had financial ties
to the company, and app users are a self-selected group, not a random sample.
- Mean cycle 29.3 days. Only 13% of cycles were exactly 28 days. About 91%
  fell in 21–35.
- Mean follicular phase 16.9 days (95% range 10–30). Mean luteal phase 12.4
  days (95% range 7–17).
- Longer cycles differ mostly in follicular length. The luteal phase barely
  changes.
- From age 25 to 45, cycle length shrinks by about 0.18 days per year.
Takeaway: phase lengths are person-specific. "28 days, ovulation on day 14"
is a textbook, not the typical case.

### A3. How well can a phase be known from the calendar?
- Johnson et al. 2018 (949 volunteers, urine hormone tests): ovulation day
  varies a lot for any given cycle length, so apps that use cycle length
  alone cannot accurately predict it.
- Sports Health 2013 (calendar-based phase assignment): counting from
  self-reported dates should not be used alone when identifying ovulation
  accurately matters. Urinary ovulation tests helped.
Implications (my reading, not a source's claim):
- Label every phase as an estimate, and show windows rather than single days.
- For completed cycles, place ovulation backwards from the next period start.
  That is better than a forward guess, but still an estimate.
- For the current cycle, show the uncertainty, don't hide it.

DECISION NEEDED: SPEC.md sets ovulation = next period minus 14 days. The data
above suggest a mean luteal phase nearer 12–13 days, with wide spread. Ask me
whether to keep 14 (simple and standard), change the default, or make it a
per-user setting. Don't change it silently: the fertile-window tests and the
coverage tests depend on it.

### A4. What research says about phase effects
This is why Nova personalizes instead of handing out phase tips.
- Exercise: McNulty et al. 2020 (meta-analysis, 78 studies) found at most a
  trivial dip in performance during the early follicular phase. The evidence
  was mostly low quality, and the authors say it doesn't support general
  guidance. They recommend a personalised approach.
- Strength training: a 2023 umbrella review (Colenso-Semple, D'Souza,
  Elliott-Sale, Front Sports Act Living 5:1054542) reports no meaningful
  phase influence on strength or training adaptation. I only saw this through
  a secondary summary, so look up the paper before relying on it.
- Mood: studies using daily ratings recorded as they happen do not support a
  universal premenstrual mood drop. In one 6-month daily study, only about
  half of mood items showed any phase link, and physical health, perceived
  stress and social support explained daily mood better than phase did.
  Looking back and reporting mood afterwards overstates cyclical change
  compared with daily ratings.
- Cognition: reviews find inconsistent results. The luteal phase is linked
  with poorer emotion-related thinking. Other kinds of cognition are less
  consistent.
- Individual differences are real: people differ in how sensitive they are to
  hormonal change. That is the case for per-person analysis and for daily
  prospective logging.

Wording rules:
- Use "tends to" and "in your data". Never "your hormones make you...".
- Don't state phase-to-energy, creativity or intuition claims as facts.
- The Mya Care infographic makes claims like "creativity peaks" and "high
  intuition". Nothing in this appendix supports them. Don't reproduce them.

### A5. Design implications for the by-phase analysis (my suggestions, evaluate)
- Fewer buckets. With about 6 cycles, 4 phases times ~10 strategies is a lot
  of comparisons, and some will look real by chance. Consider 3 buckets
  (period days / rest of follicular plus the ovulation window / luteal), or
  correct for multiple comparisons, and say which in the spec.
- Expectation bias. If I see "you're in your luteal phase" while rating my
  day, my rating may drift toward the stereotype. Consider not showing the
  phase on the daily logging screen, and revealing it only in the analysis.
- Alignment. The luteal phase is the steadier half, so align luteal days
  backwards from the next period and follicular days forwards from the
  period start.
- Hormonal contraception means no natural cycle. This isn't sourced here, but
  the Q&A already says it. DECISION NEEDED: disable the phase features for
  those users, or show a caveat?

### A6. Sources
- Cleveland Clinic, menstrual cycle: https://my.clevelandclinic.org/health/body/10132-menstrual-cycle
- Cleveland Clinic, follicular phase: https://my.clevelandclinic.org/health/body/23953-follicular-phase
- Cleveland Clinic, luteal phase: https://my.clevelandclinic.org/health/body/24417-luteal-phase
- Cleveland Clinic, normal menstruation: https://my.clevelandclinic.org/health/articles/normal-menstruation
- Bull et al. 2019 (large app dataset): https://pmc.ncbi.nlm.nih.gov/articles/PMC6710244 (doi 10.1038/s41746-019-0152-7)
- Johnson et al. 2018 (apps and calendar methods vs ovulation): https://doi.org/10.1080/03007995.2018.1475348
- Accuracy of calendar-based phase assignment, Sports Health 2013: https://pmc.ncbi.nlm.nih.gov/articles/PMC3658377/
- McNulty et al. 2020 (exercise meta-analysis): https://pmc.ncbi.nlm.nih.gov/articles/PMC7497427/
- Mood across 6 months of daily ratings (Karger): https://karger.com/pps/article/82/1/53/289418/Mood-and-the-Menstrual-Cycle
- Le et al. 2020 (cognition review): https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7226433/
- Eisenlohr-Moul commentary (individual differences, prospective ratings): https://pmc.ncbi.nlm.nih.gov/articles/PMC8429129
- Kiesner et al. 2016 (individual differences in cyclical change): https://lilia.dpss.psy.unipd.it/~massimiliano.pastore/papers/Kiesner_et_al_2016.pdf
- Utah cycle-length dataset (real cycles, used for simulator calibration): https://hive.utah.edu/concern/datasets/7h149p93m (doi 10.7278/S50d-4gxs-s4hj)

### A7. Not used, or use with care
- Mya Care page: link for further reading only, https://myacare.com/blog/what-is-cycle-syncing .
  Don't copy its text or its infographic (its footer forbids reproduction
  without written permission).
- Wellness blogs that came up in my searches were not used for any fact above.
- A 2026 medRxiv preprint on fertile-window misclassification in period
  trackers (543,167 cycles) exists: https://www.medrxiv.org/content/10.64898/2026.02.12.26346180.full.pdf .
  It is not peer reviewed and I only saw the abstract's setup, not its
  results, so read it before relying on it.
- Everything here is general information. Any health wording that ships in
  the app still needs my review.
