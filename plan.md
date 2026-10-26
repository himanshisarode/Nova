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

Pregnancy mode (old Phase 5) and Symptom Checker (old Phase 6), plus
Explain My Trend, are deferred — see SPEC.md's "Not yet built". Phase
numbers are kept as-is so earlier references still line up.

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
- requirements.txt (adds bcrypt; no AI SDK — both AI features deferred)
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
  qna_content.py (drafted 2026-10-27, awaiting review)
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
- [ ] qna page renders all 10 entries, makes zero network calls (this
      one's pure static content, not an AI feature, worth a test
      asserting no request is ever sent from this page) — after the
      wording is approved

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
- [ ] tests/test_lifestyle_link.py passes unchanged (finds the planted
      link, doesn't flag the negative control, refuses below threshold)
- [ ] tests/test_remedy.py passes unchanged
- [ ] Remedy normalization tested ("Heat Pad" and "heat_pad" pool)
- [ ] Both confirmed to make zero network calls (same test pattern as
      the qna page)

### Phase 8 — app.py
- Wires everything: login/signup flow, partner view, all in-scope
  features, consistent card styling throughout
Acceptance:
- [ ] Every in-scope feature in SPEC.md's Features list — 1–7, 9, 10,
      13, 14, 15, 16 — reachable from the UI without editing code (8,
      11, 12 are deferred)
- [ ] Medical disclaimer renders next to every prediction, fertile-
      window estimate, and irregularity flag (partner view included)
      and in every page's footer — AppTest, per SPEC.md

### Phase 9 — Dockerfile, docker-compose, README
- SQLite file must be on a mounted volume, not the container's writable
  layer — tested with multiple users' data surviving a full container
  restart, not just one user's
Acceptance:
- [ ] `docker compose up` serves the app with no errors
- [ ] Two users' data both survive `docker compose down && up`
- [ ] Full `pytest tests/` passes — final gate before calling v2 done

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
