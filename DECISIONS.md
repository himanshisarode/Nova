# DECISIONS.md — Nova Level 2

Plain-language record of every choice made for Level 2: what was
decided, what else was possible, and why. SPEC.md says *what* the app
does; this file says *why it does it that way*. Where a decision came
from the project owner it says so; everything else was decided by
Claude Code within the owner's rules, and can be changed.

---

## The four Appendix A decisions (owner's defaults)

### (a) Ovulation = next period − 14 days, as a per-user setting
- **Decided:** keep 14 as the default, store `luteal_days` per user
  (allowed 10–17), used by both the fertile window and the phases.
- **Alternatives:** keep a fixed 14; change the default to 12 or 13.
- **Why:** Bull et al. 2019 found a mean luteal phase of 12.4 days, so
  14 is a textbook value, not the typical one. But changing the default
  silently would move every existing user's fertile window and break
  the tests that pin it. A setting keeps today's behaviour for everyone
  who doesn't touch it and lets someone who knows her luteal length
  (e.g. from ovulation tests) use it. The range 10–17 is the "normal"
  range in Appendix A1.

### (b) Three phase buckets for the analysis
- **Decided:** period days / follicular (rest of follicular plus the
  ovulation window) / luteal. The display still uses the four familiar
  names, because people know them, but the statistics use three.
- **Alternatives:** four buckets; or four buckets plus a correction for
  multiple comparisons.
- **Why:** with ~6–10 cycles of data, four buckets × 10 strategies is 40
  comparisons, and some would "work" by chance. The ovulation window is
  only ~5 days a cycle and its position is the least certain (Appendix
  A3), so it would be the noisiest bucket anyway.
- **Change I made on top:** I *also* correct for multiple comparisons
  (Benjamini–Hochberg, below). Three buckets × 10 strategies is still 30
  tests; at a plain 5% level a person with no real effects would expect
  ~1.5 false "tends to go well" findings. Fewer buckets reduces the
  problem; it doesn't remove it.

### (c) No phase label on the daily logging screen
- **Decided:** the Today page never names a phase.
- **Alternative:** show it (it's informative).
- **Why:** expectation bias (Appendix A5). If the screen says "luteal"
  while you rate your day, the rating can drift toward the stereotype,
  and then the analysis would "discover" the stereotype. Phases are
  shown on the "My phases" page instead.

### (d) Hormonal contraception
- **Decided:** a settings question. If yes: the phase tracker stays but
  carries a caveat; the personalised findings, Phase Guide and Week Fit
  are switched off.
- **Alternatives:** switch everything off; show everything with a
  caveat.
- **Why:** hormonal contraception usually suppresses the natural cycle
  that the phases describe (the existing "Did You Know?" answer already
  says predictions aren't meaningful on it). A "what works in my luteal
  phase" finding would describe a phase that may not exist. Keeping the
  tracker (with the caveat) still lets her see her bleeding pattern.

---

## Data

### Strategies get their own table, not remedy_log
- **Decided:** new `daily_strategy` table + two nullable columns on
  `daily_log` (`day_rating`, `energy`).
- **Alternative:** add a "strategy" kind to `remedy_log`.
- **Why:** a remedy is tied to a symptom and rated by how much it eased
  that symptom. A strategy is tied to a day and judged against the
  whole day's rating; most days have no symptom at all. Forcing them
  into one table would mean fake symptoms or nullable symptom columns
  and would muddle Feature 16's averages.

### The strategy list (10, fixed)
walk, yoga, strength, cardio, rest day, deep-focus work, light admin,
social plans, early night, journaling.
- **Why these:** the owner's examples, plus journaling to make ten. All
  are things a person *does*, can tick in one tap, and that aren't
  health claims. Deliberately absent: anything about food, calories,
  weight or supplements (owner's rule), and "creative work" (Appendix A
  warns against creativity-peak claims, and a label would invite them).
- **Fixed, not free text:** free text can't be compared across days
  without normalising it, and it would make LLM payloads open-ended.

### Migration
- **Decided:** `db.migrate()` runs on every start, checks what exists
  and only adds missing columns/tables. No row is rewritten or copied.
- **Alternative:** a versioned migration framework (e.g. a
  schema_version table and numbered scripts).
- **Why:** there is exactly one migration and it is purely additive,
  which SQLite does safely with ALTER TABLE ADD COLUMN. A framework
  would be more machinery than the change itself. If a non-additive
  change is ever needed, that's the moment to add versioning.

---

## The 6-month gate
- **Decided:** all three of: first log ≥ 180 days ago; ≥ 4 completed
  cycles; ≥ 50% of the last 180 days logged.
- **Alternatives:** 6 completed cycles (the owner's question); a rating
  count instead of any-log density; no density rule.
- **Why 4, not 6 cycles:** 6 is too strict for long cycles. With 35–38
  day cycles (still normal), 180 days holds only 4 completed cycles, so
  a "6 cycles" rule would keep a regular user locked out for 7–8 months
  while a 26-day user unlocks at 6 months. 4 cycles is also the
  analysis's own minimum spread (below), so the gate never opens onto a
  page that can't possibly show a result.
- **Why a density rule:** "first log 180 days ago" alone is satisfied
  by someone who logged once in April. 50% means roughly every other
  day, which is realistic for a habit and gives enough rated days per
  phase.
- **Why "any log" and not "rated days":** existing users have months of
  logs but no ratings (ratings are new). The gate measures commitment;
  the analysis's own minimums decide whether there's enough *rated*
  data for each finding, and say "not enough data yet" if not.

---

## The by-phase analysis ("what works for me, by phase")

### What is compared
For each phase bucket and strategy: the day rating on days you used the
strategy vs days you didn't — **inside the same cycle and the same
phase**. That is "my own baseline for that phase".

### Why not just compare averages over all days
Two problems the owner raised:
1. **Days within a cycle aren't independent.** A good month has many
   good days; if you also happened to do yoga a lot that month, a plain
   average would credit yoga. Comparing *within* each cycle removes
   month-to-month level differences.
2. **You choose strategies by feel.** On a day you feel good you may be
   more likely to go to the gym. No statistic can separate "the gym made
   the day good" from "a good day made me go to the gym" without an
   experiment. So the wording is strictly associative and the page says
   so.

### The test: stratified permutation test
- **Statistic:** in each cycle, (average rating on use days) − (average
  on non-use days); then a weighted average of those differences across
  cycles (cycles with a more balanced split count more; weight =
  n_use·n_non/(n_use+n_non), the usual weight for a difference of
  means).
- **p-value:** "if the strategy made no difference, which days got it
  would be arbitrary." So shuffle the use/non-use labels *within each
  cycle* (never across cycles), recompute the statistic many times, and
  see how often a shuffle beats the real one. Exact when the number of
  possible shuffles is ≤ 20,000; otherwise 5,000 random shuffles with a
  fixed seed (reproducible).
- **Alternatives considered:**
  - Per-cycle differences + a sign test or t-test across cycles (treats
    each cycle as one data point). Most robust to within-cycle
    dependence, but with 6–10 cycles it can almost never reach
    significance (a sign test over 5 cycles can't go below p = 0.06
    two-sided), so it would say "no clear difference" forever.
  - A mixed-effects regression (random effect per cycle). Similar idea
    to mine, but more assumptions (normal errors on a 1–5 scale) and
    harder to explain or hand-check.
  - Welch's t-test on days (like Feature 15). Simplest, but ignores
    both problems above.
- **Why this one:** it handles the month-to-month problem, makes no
  normality assumption about 1–5 ratings, and on a small fixture the
  p-value can be worked out by hand — which is how it is tested.
- **Its limits (stated in the app):** it does *not* fix that nearby days
  inside a cycle affect each other (a good week), nor the "chosen by
  feel" problem, and the phases themselves are calendar estimates
  (Appendix A3). Findings are patterns in your logs, not causes.

### Multiple comparisons
- Benjamini–Hochberg over every pair that met the minimum, at q < 0.10.
- **Alternative:** Bonferroni (as the irregularity explanations use).
  Bonferroni over 30 tests needs p < 0.0017, which needs far more data
  than 6–10 cycles; it would almost never show anything. BH controls
  the share of findings that are false (here ≤ 10%), which matches the
  question being asked ("which of these are worth trusting?").
- Checked on simulated people (40 per row; planted effect = +1 or +0.7
  rating points on use days, two planted pairs; day noise sd 0.8,
  month-to-month sd 0.4; each strategy ticked on 25% of days, 85% of
  days rated):

  | Cycles | Effect | Planted pair found | No-effect people with any finding | People with real effects who also get ≥ 1 false finding |
  |---|---|---|---|---|
  | 6 | 1.0 | 90% / 80% | 5% | 22.5% |
  | 8 | 1.0 | 95% / 90% | 2.5% | 15% |
  | 10 | 1.0 | 95% / 100% | 0% | 17.5% |
  | 6 | 0.7 | 50% / 38% | 5% | 12.5% |
  | 10 | 0.7 | 68% / 68% | 0% | 10% |

  What this means for the viva: a strong habit-to-day link (about one
  rating point) shows up reliably after 6–8 cycles; a smaller one (0.7)
  often doesn't, even after 10. People with no real pattern are almost
  never told something tends to go well. But when real findings exist,
  BH lets roughly 1 in 6 people see one extra, false one alongside them
  — that is the price of a 10% false-discovery rate, and the reason
  every finding carries a tier and associative wording. The test suite
  pins the 8-cycle, 1.0-point row (≥ 80% found, ≤ 10% false).

### Minimums
- 8 use days in that bucket, over ≥ 4 different cycles, each of which
  also has ≥ 1 rated non-use day in that bucket.
- **Why:** 4 cycles is the smallest spread where "within-cycle" means
  anything and a single odd month can't carry the result; 8 uses means
  about 2 per cycle. Lower (e.g. 5 uses over 3 cycles) would let one
  unusual cycle carry most of a result; higher would keep period-day
  findings (only ~5 days a cycle) out of reach for many months. These
  are judgement calls, not tuned values; the simulation check in Phase
  11 tests whether they give the planned detection and false-finding
  rates.

### Confidence tiers
"strong evidence" (q < 0.01 and ≥ 6 cycles), "moderate evidence"
(q < 0.05), "early sign" (q < 0.10). These are what the LLM receives;
it can only rephrase them, never upgrade them.

---

## Demo mode
- **Decided:** one shared demo account, seeded from simulate.py with
  10 completed cycles (≈ 10 months) and planted effects (strength in
  follicular, early night in luteal, walk on period days); "Try the
  demo" on the login page; a banner on every page; read-only for logs;
  can't create or redeem invites; signup refuses @nova.invalid; LLM
  opt-ins held in the visitor's tab only.
- **Alternatives:** a fresh demo account per visitor (would fill the
  production database with throwaway accounts); a separate demo app
  (would need another deployment and link).
- **The seed is chosen, and that's disclosed:** across seeds 0–11 (10
  cycles, +1.2 points), strength/follicular and early night/luteal were
  found in 12 of 12, walk on period days in only 7 of 12 (period days
  are few — about 5 a cycle — so that bucket has the least data). One
  seed of the 12 also produced extra, false findings. The demo uses
  seed 4, where exactly the three planted effects show; the honest
  rates are the table above and these numbers, not the demo.
- **Why read-only:** the hosted app has one demo account shared by
  every visitor; if visitors could log days, the demo would drift and
  one visitor's notes could be seen by the next.
- **Why it doesn't mix:** partner linking is the only way two accounts
  touch, so it is blocked in partner.py itself; the reserved
  `.invalid` domain can never be a real email.

---

## LLM layer

### Provider: Anthropic
Checked 2026-10-30.

| | Anthropic API | Groq | Google Gemini API |
|---|---|---|---|
| Free tier | No (paid per token; the owner has credits) | Yes (rate-limited, no card) | Yes |
| Price used here | claude-opus-5-5: $4 / $20 per million input/output tokens (Haiku 5.5: $0.10 / $0.50) | free tier; paid prices not confirmed | free tier |
| Trains on inputs? | No by default for API use (privacy.claude.com, "Is my data used for model training") | No: Services Agreement §4.2, "not permitted to use Inputs or Outputs for training… unless explicitly granted permission" | **Yes on the free tier** ("used to improve our products"; human review possible) — No on paid |
| Retention | Inputs/outputs deleted within 30 days (privacy.claude.com) | Not retained by default; up to 30 days for abuse/reliability logs; Zero Data Retention available | Not checked in detail |
| Could not verify | Exact cost per call (depends on output length) | Whether the agreement fully binds free self-serve accounts; free-tier limits per model (the docs table is labelled "Developer plan") | Google's own current terms (only seen quoted second-hand) |

- **Decided:** Anthropic. The owner already has API credits, the
  no-training and 30-day deletion statements come from Anthropic's own
  pages, and the SDK supports structured JSON output, which makes
  validation simpler. Gemini's free tier was ruled out because it may
  train on and human-review inputs. Groq was the best *free* option and
  remains the fallback if credits run out; swapping is one file
  (llm.py).
- **Model:** `claude-opus-5-5` at effort "low". The Claude API guidance
  is to default to the current Opus and leave any downgrade for cost to
  the owner. Each call is small (~1–2k tokens in, < 1k out), so the cost
  per call is a few cents; switching to `claude-haiku-5-5` (~40×
  cheaper) is a one-line change in llm.py — the owner's call.
- **Server-side fallback** (`fallbacks: "default"`) is switched on: if
  the model declines, Anthropic retries on another Claude model inside
  the same request. It never leaves Anthropic. Can be removed in one
  line.

### Both LLM features are opt-in
- The LLM layer section's table said Phase Guide needs no opt-in; the
  owner's non-negotiable rule says both are off until the user opts in.
  The stricter rule wins. Phase Guide sends no user text, so its notice
  is short; Week Fit's notice warns about names, contact and health
  details.
- The template versions need no opt-in: they never leave the machine.

### Caps: Phase Guide 3/day, Week Fit 5/day per user
- As proposed in the spec. Every attempt counts, including failures,
  and the count is taken before sending, in one database transaction,
  so double-clicks and retries can't exceed it. Phase Guide is in any
  case stored once per completed cycle, so in normal use it runs about
  once a month; the cap only matters for retries after failures.

### Validation
- Both calls ask for JSON with a fixed schema (structured output), then
  local code checks it: Phase Guide is rejected if it names any
  strategy that wasn't supplied for that phase, any banned word
  (medical/hormone/causal wording, "creativity peaks"-type claims), or
  lacks "tend"; Week Fit drops any strategy not in that day's list (and
  shows that day's template), rejects sentences over 25 words or with
  banned words, and rejects the whole reply if the structure is wrong.
- **Honest limit:** code can't check that a Week Fit sentence fairly
  reflects the user's note. It is shown next to the note so she can
  judge it.

### Week Fit near a phase boundary
- For each coming day, try every next-period start the Honest range
  allows; collect every phase the day could be in. If more than one,
  only strategies that tend to go well in *all* of them are offered; if
  none qualify, the day says "your phase is uncertain that day and
  nothing in your data clearly fits both". Once the period is late,
  every day is "luteal or period".
- **Alternatives:** pick the most likely phase (hides the uncertainty,
  which Appendix A3 says not to do); offer the union (would suggest
  things that only fit one of the phases).

### Logging and storage
- No payload, note or model reply is logged. Week Fit notes live only
  in the page's session for the current screen. A validated Phase Guide
  is stored (it contains only labels and the model's phrasing of them).

---

## "Did You Know?" (2026-10-31)

- **Decided:** 21 entries in three sections — Cycle syncing (3), Your
  cycle's phases (6), Common questions (12) — instead of adding all 16
  drafted entries to the original 10 (26).
- **Why not 26:** several drafts repeated each other or an existing
  entry. Merged rather than repeated:
  - "Which hormones are involved?" → its facts now sit in the period,
    follicular and luteal answers.
  - "Why does my cycle length change?" and the original "Does ovulation
    always happen on day 14?" → one ovulation entry.
  - "How long should a period last?" and "Is a heavy flow always a
    problem?" → one entry, keeping every safety sign from the original.
  - "Why track a cycle at all?" → dropped; the app itself makes that
    case, and the doctor entry covers when tracking helps most.
- **Length:** answers are 3–6 sentences, the same as the original ten.
  Drafts were kept word for word except where merged, plus two links to
  Nova itself ("Does cycle syncing work?" points to "What works for me";
  the phases entry explains Nova's three groups).
- **Facts checked against Cleveland Clinic (2026-10-31):** the egg lives
  about 12–24 hours, sperm up to about five days, and pregnancy is
  possible from about five days before ovulation to one day after — so
  the draft's "fertile window ends on the day of ovulation" was changed
  to "to a day after", which also matches Nova's own fertile-window rule.
  PMDD: symptoms in the week or two before a period that ease after it
  starts, with intense low mood, anxiety or irritability; one line added
  on getting help straight away with thoughts of self-harm, as Cleveland
  Clinic's page does.
- **21–35 vs 24–38 days:** the draft's doctor entry said "less than 21
  or more than 35 days apart". That is the older range many patient
  pages still give (including part of Cleveland Clinic's page). FIGO's
  2018 definitions, which Nova's irregularity flag and the original
  "28 days" answer use, say 24–38 days for adults. The entry now says
  24–38, so the Q&A and the app never contradict each other; a test
  checks it. Viva answer: both are "normal ranges"; 21–35 is the older
  convention, 24–38 is the current international (FIGO) definition, and
  Nova picked one and uses it everywhere.
