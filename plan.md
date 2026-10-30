# PLAN.md — Nova (v2 implementation plan)

Reads against the v2 SPEC.md. Supersedes Interval_PLAN.md entirely — that
file was written before accounts and partner sharing existed; don't build
off it.

Everything is built fresh in `nnova/` — no code is copied from any earlier
version, so every phase below is a full implementation, not a migration.

## Build order and why
Design system first this time (not last, like v1) — every page built
after it should already look right instead of getting restyled at the
end. Then auth, because every other table now needs a user_id, so
nothing else can be meaningfully tested until accounts exist. The core
(db/simulate/predict/irregularity) comes next, written per-user from the
start. Partner sharing needs the core's read paths to exist, so it
follows. Charts/export/Q&A, the two local-stats features, app.py, and
Docker close it out.

Pregnancy mode (old Phase 5) and Symptom Checker (old Phase 6) are
deferred — see SPEC.md's "Not yet built". Explain My Trend was dropped;
SPEC.md's LLM layer replaces it. Phase numbers are kept as-is so earlier
references still line up.

## Estimate (two-week build ≈ 10 working days)
| Phase | What | Est. days |
|---|---|---|
| 0 | Scaffolding + design system | 0.5 |
| 1 | auth.py | 0.5–1 |
| 2 | db.py (full, multi-user) | 1 |
| 3 | simulate.py, predict.py, irregularity.py (full) | 2–2.5 |
| 4 | partner.py | 1 |
| 7 | charts.py, export.py, qna_content.py (full) | 1.5–2 |
| 7.5 | lifestyle_link.py, remedy.py | 0.5–1 |
| 8 | app.py | 1.5–2 |
| 9 | Docker, README | 0.5–1 |
| | **Total** | **9–12** |

That's tight — at the high end it overruns two weeks with no buffer.
Phase 3 is the biggest risk (the statistical method has to be designed,
not ported — see SPEC.md Open Questions). If it slips, the first things
to trim, in order: the PDF half of the doctor export (keep CSV), then the
SHAP explanations on irregularity flags (keep the flag itself). Neither
is cut yet; flagging now so it's a decision, not a surprise.

### Phase 0 — scaffolding + design system
- requirements.txt (adds bcrypt; no AI SDK — no AI feature was in scope
  then; the SDK arrives with Phase 10)
- .streamlit/config.toml with the pastel palette from SPEC.md
- assets/ with custom CSS for cards/shadows/whitespace; static/fonts/
  with self-hosted Quicksand; theme.py to apply both on any page
- One throwaway demo page just to confirm the look before building real
  features on top of it
Acceptance: a blank page actually looks like the pastel/card design, not
default Streamlit gray. — Done, approved 2026-10-27 (screenshots in
design_preview/).

### Phase 1 — auth.py
- users table, signup, login, bcrypt password hashing, session handling
  (logged-in user held in session state for the life of the tab — no
  persistent cross-restart login)
- auth functions take an open sqlite3 connection; connection management
  (file location, pragmas) belongs to db.py in Phase 2
Acceptance:
- [x] A signed-up user can log back in after an app restart (their
  account persists; their session doesn't need to)
- [x] No plaintext password anywhere in the DB file (test asserts this
  directly)
- [x] tests/test_auth.py covers signup/login/bad-password paths

### Phase 2 — db.py, multi-user
- daily_log (primary key (user_id, date)), daily_symptom (user_id, date,
  symptom), cycle — all CRUD functions take a user_id
- db.connect() owns connection setup (file location, foreign keys on,
  schema creation including auth's users table)
Acceptance:
- [x] Data persists across reopening the DB file
- [x] Two different users' data stays separate in the same file
- [x] Period-start/cycle rule checked against hand-worked dates

### Phase 2.5 — before Phase 3
- Period rule: raise the gap from 2 to 7 non-bleeding days (one
  constant in db.py); replace the old 2-day boundary test with the
  day 1 / days 2–3 / day 4 scenario, plus 6-day (same period) and
  7-day (new period) boundary tests
- Medical disclaimer: constant + render helper in theme.py, a test
  that the code text matches SPEC.md verbatim, and the disclaimer shown
  on the demo page's prediction card and footer
Acceptance:
- [x] Period-rule boundary tests pass (and fail against the old 2-day rule)
- [x] Disclaimer text in code matches SPEC.md; demo renders it in the
      prediction card and footer (tests/ui_checks.py, reused in Phase 8)

### Phase 3 — simulate.py, predict.py, irregularity.py
- Methods as approved, recorded in SPEC.md Features 2, 3, 5
- Additions made during the build (beyond the approved proposal): SHAP
  factors are gated by a permutation test (Bonferroni), and per-cycle
  factors skip bleeding days — without these, simulated people with no
  real pattern were given a confident-sounding explanation
Acceptance (measured on simulated people):
- [x] Shown range covers 89.7% with 15% irregular cycles (target
      85–95%); unrounded interval 90.6% on clean data
- [x] Irregularity recall 96.9% (target ≥ 80%), false-flag rate 3.2%
      (guard ≤ 10%)
- [x] Planted stress link found; no-pattern control rarely explained

### Phase 4 — partner.py
- Invite-code generation, linking, read-only access enforced at the
  query layer (not the UI — a partner-scoped query function should
  physically be incapable of writing)
- One-way links: inviter's data is shared, invitee is the viewer
- Codes single-use, expire 48h after creation if unused
- Partner-scoped reads return dashboard, Cycle Trends, and predictions
  only — never raw daily logs or remedy_log
Acceptance:
- [x] Linked partner sees the shared view, any attempted write is
      rejected at the function level, not just hidden from the UI
      (read-only SQLite connection; verified the tests fail if it's
      made writable)
- [x] Partner-scoped queries can't reach daily_log rows or remedy_log
      (PartnerView's public API is pinned by a test)
- [x] Reused code and expired code (>48h) both fail, tested
- [x] A→B link doesn't grant A access to B
- [x] Revoke removes access immediately, even for an already-open view
      (verified the test fails without the per-read check)

### Phase 5 — pregnancy.py — DEFERRED
See SPEC.md "Not yet built".

### Phase 6 — symptom_checker.py — DEFERRED
See SPEC.md "Not yet built".

### Phase 7 — charts.py, export.py, qna_content.py
- charts.py, export.py: full per-user implementations, styled per the
  Phase 0 design system (export contents: SPEC.md Features 6–7)
- Q&A wording is reviewed separately before it goes into
  qna_content.py (drafted and approved 2026-10-27)
- qna_content.py: the 10 Q&A pairs as a static data structure (list of
  {question, answer} — keep content separate from whatever renders it, so
  the actual wording is easy to review in a diff on its own, not buried
  inside UI code)
Acceptance:
- [x] Export test: CSV/PDF contain the user's data and only that user's,
      none of the excluded details; reasons never name a cause
- [x] Delete-all: raw-file grep finds nothing afterwards (and the
      control without secure_delete does find it)
- [x] Charts plot hand-checked values; empty data gives no chart
- [x] qna page renders all 10 entries, makes zero network calls (this
      one's pure static content, not an AI feature, worth a test
      asserting no request is ever sent from this page)

### Phase 7.5 — lifestyle_link.py, remedy.py
Both are local stats, not API calls — deliberate, see SPEC.md's
Architecture section for why. Build against the fixed acceptance tests
already in tests/ (test_lifestyle_link.py, test_remedy.py) — these were
hand-written with independently computed expected values; don't
regenerate or rewrite them.
- lifestyle_link.py: `check_lifestyle_link(cycles, tag)`; a cycle is
  tagged if the tag appears on any day in it; two-sided Welch's t-test at
  alpha=0.05; "not enough data" below 3 per group
- remedy.py: `remedy_effectiveness(logs)`; extend the daily logging form
  with optional remedy + relief-rating fields (remedy_log table); remedy
  text normalized (lowercase, strip, spaces→underscores); average by
  (symptom, remedy) pair; 3+ instances = "ranked" (even if alone),
  below that = "not enough data"
Acceptance:
- [x] tests/test_lifestyle_link.py passes unchanged (finds the planted
      link, doesn't flag the negative control, refuses below threshold)
- [x] tests/test_remedy.py passes unchanged (git confirms both files are
      byte-identical to the first commit)
- [x] Remedy normalization tested ("Heat Pad" and "heat_pad" pool)
- [x] Both confirmed to make zero network calls (sockets blocked during
      the calls, with a control proving the block works; neither module
      imports anything network-capable)

### Phase 8 — app.py
- Wires everything: login/signup flow, partner view, all in-scope
  features, consistent card styling throughout
Acceptance:
- [x] Every in-scope feature in SPEC.md's Features list — 1–7, 9, 10,
      13, 14, 15, 16 — reachable from the UI without editing code (8,
      11, 12 are deferred). Feature 14's page exists but shows a
      "being written" state until the Q&A wording is approved.
- [x] Medical disclaimer renders next to every prediction, fertile-
      window estimate, and irregularity flag (partner view included)
      and in every page's footer — AppTest, per SPEC.md (verified the
      test fails if a card's disclaimer is removed)
Found while checking the running app:
- With varied cycles the fertile window became very wide → resolved:
  above a 9-day spread the card suggests seeing a doctor instead
- The "any day" tag rule leaves Lifestyle-Link short of untagged cycles
  → parked for now (SPEC.md Open Questions)

### Phase 9 — Dockerfile, docker-compose, README
- SQLite file must be on a mounted volume, not the container's writable
  layer — tested with multiple users' data surviving a full container
  restart, not just one user's
Acceptance:
- [ ] `docker compose up` serves the app with no errors
- [ ] Two users' data both survive `docker compose down && up`
  Docker isn't installed on the dev machine, so both are verified in
  GitHub Actions instead (.github/workflows/tests.yml): the full suite
  runs on Linux on every push, with NOVA_REQUIRE_DOCKER set so the
  persistence test fails rather than skips if Docker were missing.
- [x] Full `pytest tests/` passes — final gate before calling v2 done
      (with the Docker live check skipped, see above)

## Level 2 (branch `level2`) — Phases 10–16
Reads against SPEC.md Features 17–23, "Constraints" and "LLM layer
(Level 2)"; every choice is explained in DECISIONS.md. One commit per
phase, full `pytest tests/` before each, and the app stays runnable and
deployable at every commit (new modules are unused until Phase 15
wires them in; db.migrate() is additive, so an early deploy is safe).

### Estimate (≈ 12 hours available; budget ≈ 8 for the build)
| Phase | What | Est. hours |
|---|---|---|
| — | spec.md, plan.md, DECISIONS.md | 1 |
| 10 | phases.py, "what works" log in db.py, gate.py, migration | 1.5 |
| 11 | whatworks.py + hand fixture + simulation check | 1.5 |
| 12 | llm.py, caps, mocked-provider tests, Phase Guide (→ Level 1) | 1.5 |
| 13 | demo.py (+ simulate.py strategies) | 0.75 |
| 14 | week_fit.py (→ Level 2) | 1 |
| 15 | app.py wiring, exports/delete, migration check script | 1.5 |
| 16 | stretch: Week Fit evaluation script | 0.5 |
| | **Total** | **≈ 9.25** |

Honest view: that is over the 8-hour budget by about an hour, and
Phase 15 (UI) is where overruns usually happen. If it runs long, cut in
this order: Phase 16 (mark "not yet built"); then the confidence
tiers (keep one); then the demo's daily re-seeding (seed once instead).
Never cut: the non-negotiable rules, the fixture, the payload tests.

### Phase 10 — phases.py, "what works for me" log, gate.py
- db.py: STRATEGIES; daily_log.day_rating/energy; daily_strategy;
  user_settings; db.migrate() (additive only); LogEntry gains optional
  day_rating, energy, strategies (defaults keep every existing call
  working); save_logs() bulk path; settings get/set; delete_account
  covers the new tables
- predict.fertile_window(prediction, luteal_days=LUTEAL_DAYS)
- phases.py: periods per cycle, day → phase for completed cycles,
  current-cycle windows, bucket(), candidate_buckets()
- gate.py: the three conditions + progress
Acceptance:
- [ ] tests/test_phases.py: hand-worked cycles (24, 29, 38 days; L 12
      and 14), current-cycle windows, late period, < 3 cycles
- [ ] tests/test_gate.py: each boundary on its own
- [ ] tests/test_migration.py: old-schema database migrates, rows
      unchanged; running migrate twice is a no-op
- [ ] Existing suite unchanged and passing

### Phase 11 — whatworks.py
- Stratified permutation test + BH, minimums, tiers, describe()
- tests/test_whatworks_fixture.py written by hand first (expected
  values worked out in comments), then frozen
- simulate.py: strategy/rating simulation on its own RNG stream, so
  every existing simulate test keeps its numbers
Acceptance:
- [ ] Fixture: planted effect found with the exact statistic/p-value;
      negative control not found; below-minimum pairs refused
- [ ] Simulation: planted effects found in ≥ 80% of people; ≤ 10% of
      no-effect people get any "tends to go well"
- [ ] whatworks.py imports nothing network-capable (same AST check)

### Phase 12 — llm.py + Phase Guide (Level 1)
- llm.py: Anthropic SDK, model constant, key from env only, caps in
  llm_usage, CALL_TYPES = (phase_guide, week_fit), no payload logging,
  provider errors → LLMUnavailable; injectable http client for tests
- phase_guide.py: payload(), template(), validate(), generate() with
  storage in phase_guide (once per completed cycle)
- .env in .gitignore; requirements.txt adds anthropic
Acceptance:
- [ ] Real request body (captured by an httpx2 MockTransport) holds
      only labels, tiers and two numbers
- [ ] Unsupplied strategy / medical wording / non-associative wording
      → rejected → template
- [ ] Cap blocks call N+1 per user and per call type
- [ ] No key, network error, 500, bad JSON → template, app usable
- [ ] Off until opt-in; only phase_guide.py and week_fit.py import llm
- [ ] No API key string in any tracked file (test greps git ls-files)

### Phase 13 — demo.py
- simulate.py planted per-phase strategy effects; demo.seed(conn,
  today); ensure_demo(); is_demo flag; partner.py refuses demo
  invites; auth.signup refuses @nova.invalid
Acceptance:
- [ ] ≥ 8 months seeded; planted effects found end to end
- [ ] Demo can't save logs, create or redeem invites (function level)

### Phase 14 — week_fit.py (Level 2)
- Notes check (≤ 200 chars, email/phone patterns), payload(),
  template(), validate() (per-day drop → that day's template; bad
  structure → whole template), generate(); nothing stored
Acceptance: SPEC.md LLM layer list (payload, injection, notes never in
the DB or logs, cap, failure, opt-in/revoke)

### Phase 15 — wiring + migration
- Today: strategies, day rating, energy (no phase label)
- New pages "My phases" (tracker, gate progress, findings, Phase
  Guide) and "Plan my week" (Week Fit); Settings: luteal days,
  contraception, opt-ins with the provider notice; login: "Try the
  demo"; demo banner; exports and delete-all extended (the exact-file
  list in test_export.py grows by the new files — a spec change, the
  test isn't loosened)
- scripts/check_migration.py: copies a database file, migrates the
  copy, compares every pre-existing table row by row, prints counts
- Production (done by the owner, not by Claude Code; exact commands in
  README "Upgrading to Level 2"): snapshot the volume and download a
  copy of /data/nova.db; run check_migration.py on that copy locally;
  `fly secrets set ANTHROPIC_API_KEY=...` (never in the repo);
  `fly deploy` (same app name nova-aug47w, so the link doesn't change);
  log in and compare row counts with the pre-deploy numbers
Acceptance:
- [ ] Every Level 2 feature reachable; disclaimer in every card that
      shows a phase or finding; pre-gate users see progress only
- [ ] Migration check passes on a copy of the local data/nova.db
- [ ] Full suite passes (incl. Docker)

### Phase 16 — stretch: Week Fit evaluation script
- eval/week_fit_samples.json (≈ 15 hand-built weeks);
  scripts/eval_week_fit.py runs the real provider (needs the key,
  never run by pytest), reports validation-pass rate and writes a
  sheet for the owner's sensible-fit marks; numbers go in README with
  the small-sample caveat
- If not reached: SPEC.md lists it under "Not yet built"

## Risks / ambiguities
- Phase 2/3 depend on definitions that used to be inherited from v1 and
  now aren't written anywhere (SPEC.md Open Questions). These need
  settling before Phase 2 starts, or Phase 2/3 will end up guessing.
- Partner read-only enforcement at the query layer is a correctness
  requirement, not a nice-to-have — worth double-checking in review, not
  just trusting that "it probably works."
- Passwords stay hashed even though general privacy strictness was
  relaxed for this version — this one line didn't move, and shouldn't.
- No architecture decision here assumes real deployment scale (two users
  is the actual target, not thousands) — if "very good project" ever
  means "handle real traffic," that's a separate, larger conversation
  about moving off SQLite, not something this plan quietly prepares for.
- If the deferred Symptom Checker is ever built, its symptom/urgent lists
  are a first draft, not clinically reviewed — they'd need an actual
  clinician's review before anyone beyond a demo uses it.

## Output files
(matches SPEC.md's Output Files section exactly — see there)

## Approval
Same scoped-approval convention as before: approve one phase at a time.
Phase 0 first — demo page reviewed and approved before Phase 1.
