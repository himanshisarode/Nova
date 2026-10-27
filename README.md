# 🌙 Nova

A cycle-tracking app built around **honest predictions**: every number traces
back to an actual statistic computed from your own logged data, and the app
says "not enough data yet" rather than guessing. For one person, optionally
sharing a read-only view with a partner they invite.

> Nova's predictions, trend charts, and irregularity flags are based on
> statistical patterns in your own logged data. This is general information,
> not medical advice, and not a diagnosis. Cycle length, ovulation timing, and
> what counts as 'irregular' can be affected by many things this app doesn't
> know about. If something feels wrong, changes suddenly, or worries you,
> please talk to a doctor or gynecologist - don't rely on this app alone.

A course project (UMC301). Not clinically reviewed or certified.

## What it does

| | Feature | How |
|---|---|---|
| 📝 | Daily check-in | Flow, mood, symptoms, lifestyle tags (poor sleep, high stress, travel), optional remedy + relief rating |
| 🗓️ | Period prediction | **Honest**: a 90% prediction interval (t-distribution) from your last ≤12 cycles. **Simple**: one date. Both need 3 completed cycles |
| 🌿 | Fertile window | Ovulation ≈ 14 days before the predicted period; labelled as an estimate, never contraception |
| 📈 | Cycle Trends | Cycle length (irregular cycles marked), period length, symptom frequency |
| 🔍 | Irregular cycles | Outside 24–38 days, or > 7 days from your own usual; SHAP explanation only when a factor passes a significance test |
| 🔗 | Lifestyle links | Welch's t-test: do cycles with a tag differ in length? |
| 🫖 | What helps | Average relief per remedy, once it's been logged 3+ times |
| 🩺 | Doctor export | One-page PDF + CSV, cycle-level only (no mood, tags or remedies) |
| 💌 | Partner sharing | Single-use 48h invite codes; one-way, read-only, revocable; enforced by a read-only database connection |
| 📦 | Your data | Export everything as a ZIP; delete everything (overwritten on disk via SQLite `secure_delete`) |

**Not yet built** (described in `spec.md`): pregnancy mode, Symptom Checker,
Explain My Trend. Nothing in the current app calls any external API or sends
data anywhere — there are no API keys to configure.

## Run it locally

Python 3.14:

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows; on macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Open http://localhost:8501 and create an account. Data is stored in
`data/nova.db` (or wherever `NOVA_DB_PATH` points).

## Run it with Docker

```bash
docker compose up --build
```

Open http://localhost:8501. The port is published on this machine only.

The database lives on the named volume `nova-data`, mounted at `/data` — not
inside the container — so it survives `docker compose down` followed by
`docker compose up`. **`docker compose down -v` deletes the volume and all
data in it.**

## Deploy to Fly.io

`fly.toml` runs the same Docker image on one Fly machine, with the database
on a 1 GB Fly volume mounted at `/data`. Install
[flyctl](https://fly.io/docs/flyctl/install/), then:

```bash
fly auth login
fly launch --copy-config --no-deploy   # creates the app; rename it if "nova-cycle" is taken
fly volumes create nova_data --size 1 --region maa
fly deploy
fly scale count 1                      # one machine only: SQLite can't be shared
```

Open the URL `fly deploy` prints (`https://<app>.fly.dev`). Later deploys are
just `fly deploy`; the volume and its data stay. Notes:

- **Never run more than one machine.** Each machine would get its own,
  separate database.
- The machine stops when idle and starts on the next visit (a few seconds).
  Signed-in tabs have to log in again afterwards.
- Fly snapshots volumes daily, but keep your own copy too:
  `fly ssh sftp get /data/nova.db nova-backup.db`.
- Unlike Docker locally, the app is public on the internet. Accounts are
  password-protected, but this is a course project, not a certified health
  service; don't store real health data you aren't comfortable with.

## Tests

```bash
pytest tests/
```

A few minutes; most of that is the simulation-based checks and importing
SHAP. Highlights:

- Prediction intervals checked for coverage on simulated people; irregularity
  detection for recall and false-flag rate.
- `tests/test_lifestyle_link.py` and `tests/test_remedy.py` are hand-written
  acceptance tests with independently computed answers — fixed, not to be
  regenerated.
- Partner access: writes through the partner's connection fail at the
  database; revoking cuts off an already-open view.
- Deletion: the raw database file is searched afterwards for the deleted
  user's details.
- The disclaimer is checked to render inside every prediction and flag card
  and every page footer, and to match `spec.md` word for word.
- `tests/test_docker.py` runs a full `down`/`up` persistence check when Docker
  is installed, and is skipped otherwise. GitHub Actions runs the whole suite
  on Linux on every push, where Docker is required.

## Layout

```
app.py              Streamlit pages
theme.py            design system helpers + the disclaimer text
auth.py             accounts, bcrypt hashing, tab session
db.py               SQLite schema, per-user logs, derived cycles, remedies, delete
partner.py          invite codes, links, read-only PartnerView
predict.py          Simple/Honest prediction, fertile window
irregularity.py     flag rule, SHAP explanations
lifestyle_link.py   Lifestyle-Link Finder
remedy.py           Remedy Effectiveness
charts.py           Plotly charts
export.py           doctor PDF/CSV, export-my-data ZIP
simulate.py         synthetic cycle histories for tests
qna_content.py      "Did You Know?" content (10 fixed entries)
spec.md, plan.md    what's being built and in what order
```

`design_demo.py` is the Phase 0 design preview (`streamlit run design_demo.py`).
