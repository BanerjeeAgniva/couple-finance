# Couple Finance

[![CI](https://github.com/BanerjeeAgniva/couple-finance/actions/workflows/ci.yml/badge.svg)](https://github.com/BanerjeeAgniva/couple-finance/actions/workflows/ci.yml)

**The shared wallet for two people whose incomes aren't equal.**

Roommates split 50/50. Couples don't live 50/50. When one partner earns ₹90k and the other ₹60k,
splitting rent down the middle quietly makes the lower earner carry more. Couple Finance fixes that in
one decision: **set your income ratio once, and every expense splits by it — automatically, forever.**
No spreadsheets, no "I'll pay you back," no mental math. Just add what you spent; the app always knows
who owes whom, and settles it over UPI in one tap.

Shared password, no per-user accounts. Built as a real, deployed product — FastAPI backend, zero-framework
front end, money stored to the paise, UPI settlement, receipt OCR, and a hosted database, running live and free.

---

## See it move

**A 60-second walk through the whole app** — add an expense, pick a brand, then activity, settle-up, trends and notes.

<p align="center"><img src="screenshots/walkthrough.gif" alt="Couple Finance — full walkthrough" width="300"></p>

**Whose turn to pay? One tap.** The payer slides between the two of you — teal for one, coral for the
other — and the whole ledger re-reasons instantly.

<p align="center"><img src="screenshots/payer-shift.gif" alt="Sliding payer selector" width="300"></p>

---

## What it does

- **Income-ratio split** — set both incomes once; every expense splits automatically.
- **Who paid → who owes** — a running, directional settle-up balance, always on top.
- **One-tap UPI settle** — deep-link + QR pay the exact amount to the right person; full or partial.
- **Brand-aware categories** — 21 categories, 14 of them the apps you actually use (Amazon, Swiggy,
  Zomato, Zepto, Blinkit, Instamart, Flipkart, Rapido, Uber, UrbanClap…), each with its own color + icon.
- **Receipt OCR** — snap a bill; it reads the total and merchant and fills the form.
- **Per-expense override** — send one expense 50/50 or fully custom without touching the global ratio.
- **Recurring** — rent/wifi/etc. auto-posted each month to the right payer.
- **Trends** — monthly spend by person, per-person totals, per-category breakdown.
- **Filter by category** — zoom the activity feed to one category (count + total), deep-linked at `#activity/<category>`.
- **Shared notes & checklists**, **profile photos**, dark mode, and **CSV export**.

---

## The screens
*Dark mode, seeded with two months of sample data.*

### 00 · The "aha" — set the ratio once
Type both incomes and the split comes alive (60 / 40 here). Fairness by income, decided once.
![Onboarding](screenshots/00-onboarding.png)

### 01 · Home — always know who owes whom
Every screen opens on a directional balance: two faces, an arrow, a number. Adding an expense takes seconds.
![Home](screenshots/01-home-add.png)

### 02 · One tap to switch payer
Tap the other person — the pill slides, the color flips. No dropdowns, no "who paid?" friction.
![Payer switch](screenshots/02-payer-nandini.png)

### 03 · Where they actually spend
The category picker speaks the language of modern Indian spending — 21 categories, 14 of them the apps you
open every day, each with its own color and icon.
![Categories](screenshots/03-categories.png)

### 04 · Fair by default, flexible when you need it
Splits default to the income ratio, but any single expense can go 50/50 or fully custom.
![Custom split](screenshots/04-custom-split.png)

### 05 · Snap the receipt, skip the typing
Point the camera at a bill; OCR reads the total and merchant and fills the form.
![Scan receipt](screenshots/05-scan-receipt.png)

### 06 · The feed that sells itself
Two months of real life — each row a face, a brand, a date, the amount, and exactly how it split.
![Activity](screenshots/06-activity.png)

### 07 · Settle in one tap over UPI
A UPI deep-link and a QR pay the exact amount to the right person. The balance updates the moment it's paid.
![Settle up](screenshots/07-settle-upi.png)

### 08 · Trends — where the money goes
Monthly spend split by person, per-person totals, and a full category breakdown.
![Trends](screenshots/08-trends.png)

**Spend history** — tap any of your most-used categories to chart its spend over time, like a
price-history graph: the range it moved through and where this month lands, each category in its own color.
![Spend history](screenshots/spend-history.png)

### 09 · Recurring — rent and bills post themselves
Set rent and broadband once; they auto-post every month on the right day, to the right payer.
![Recurring](screenshots/09-recurring.png)

### 10 · Shared notes & checklists
Trip budgets, shopping lists, reminders — pinned, searchable, with tappable checklists.
![Notes](screenshots/10-notes.png)

### 11 · Make it yours
Names, incomes (the ratio), UPI IDs with live validation, profile photos, categories, theme, and CSV export.
![Settings](screenshots/11-settings.png)

### 12 · Same app, bigger screen
Fully responsive — the phone experience scales to a clean desktop workspace.
![Desktop](screenshots/12-desktop.png)

### 13 · Zoom into one category
Filter the activity feed to a single category — the dropdown shows a running **count and total** for
just that category, and the view deep-links to `#activity/<category>`, so a filtered feed is bookmarkable
and shareable.
<!-- screenshot pending: screenshots/13-activity-filter.png — capture against the live site after deploy -->

---

## Architecture

**We've used a modular monolith** — a resource-oriented (router-per-resource) FastAPI app with a
functional core (`money.py` is pure, zero imports) and a single composition root (`app.py`). One
deployable, split into focused modules; the FastAPI-idiomatic layout, deliberately *not* the heavier
layered / hexagonal / clean-architecture styles that a two-user app this size doesn't need.

Three clean tiers — a static **frontend**, a FastAPI **backend**, and a SQLite/Turso **database**.
The browser only ever talks to the backend over HTTP; the backend is the only thing that touches the DB.

| Tier | Lives in | What it is | Talks to |
|------|----------|------------|----------|
| **Frontend** | `static/` (`index.html`, `app.js`, `js/`) | Zero-framework HTML/CSS/JS, served as static files | → Backend, via `fetch` HTTP calls |
| **Backend** | `app.py` + `routers/*` + `auth`, `money`, `config` | FastAPI app: 9 feature routers over 4 shared modules | ← Frontend · → Database |
| **Database** | `db.py` → `couple_finance.db` **or** Turso (hosted libSQL) | Rows, balances, migrations. Same code, swaps by env var | ← Backend only |

**Backend module map** — dependencies only ever point *downward*; no router imports another router, no cycles:

```
                         BROWSER  (static/ — HTML/CSS/JS frontend)
                            │  HTTP  (fetch)
                            ▼
┌─────────────────────────────────────────────────────────┐
│  app.py   — composition root (48 lines)                  │
│  • builds FastAPI app, includes all routers              │
│  • serves index.html + /static, runs init_db()/migrate() │
└─────────────────────────────────────────────────────────┘
                            │ mounts 9 routers
      ┌──────────┬──────────┼──────────┬──────────┬─────────┐
      ▼          ▼          ▼          ▼          ▼         ▼
  session    settings   expenses   recurring   ledger   insights   ocr   notes   export
  (login)   (ratio/…)  (add/list)  (rules)    (balance) (charts)  (rcpt)  (memo) (csv)
      │          │          │          │          │         │       │       │      │
      └──────────┴──────────┴────┬─────┴──────────┴─────────┴───────┴───────┴──────┘
                                 │ every router leans on the same 4 modules
             ┌───────────────────┼───────────────────┬──────────────────┐
             ▼                   ▼                   ▼                  ▼
        ┌─────────┐        ┌──────────┐        ┌──────────┐      ┌───────────┐
        │  auth   │        │   db     │        │  money   │      │  config   │
        │ token / │        │ SQLite/  │        │ PURE     │      │ constants │
        │ require │        │ Turso    │        │ domain:  │      │ (paths,   │
        │ _auth   │        │ rows,    │        │ split,   │      │  names,   │
        │         │        │ balance, │        │ balance, │      │  env)     │
        │         │        │ migrate  │        │ upi,ocr  │      │           │
        └────┬────┘        └────┬─────┘        └──────────┘      └─────┬─────┘
             │                  │              (no deps —              │
             └──────────────────┴──────── depends on config ──────────┘
                                          │
                                          ▼
                              DATABASE  (couple_finance.db / Turso)
```

- **`money.py`** is pure domain — zero imports of the others, so `test_money.py` tests it in isolation.
- **`config.py`** is the leaf everything stands on.
- The **db** tier is the same code whether it hits a local `.db` file or hosted Turso — chosen by the `TURSO_*` env vars.

## Run locally
```bash
pip install -r requirements.txt
export APP_PASSWORD=yourpassword
export SECRET_KEY=$(openssl rand -hex 32)
uvicorn app:app --reload
# open http://localhost:8000
python -m tests.test_money    # money-math checks
```

## Deploy — Render + Turso (card-free, persistent)

The app uses plain `sqlite3` locally and **Turso** (hosted libSQL) automatically when
`TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` are set. No code change needed to switch.

1. **Turso DB** (one-time):
   ```bash
   turso db create couple-finance
   turso db show --url couple-finance        # -> TURSO_DATABASE_URL (libsql://...)
   turso db tokens create couple-finance     # -> TURSO_AUTH_TOKEN
   ```
   <img width="2930" height="1040" alt="image" src="https://github.com/user-attachments/assets/801fe4c6-ff42-4ab8-8d7d-06781e493ed4" />

2. **Render**: New + → **Blueprint** → pick this repo (`render.yaml` is detected).
   Then set the env vars: `APP_PASSWORD` (shared password), `TURSO_DATABASE_URL`,
   `TURSO_AUTH_TOKEN`. `SECRET_KEY` is auto-generated.
   <img width="2840" height="1686" alt="image" src="https://github.com/user-attachments/assets/8a4b752b-e774-4e06-9838-c2f2c3dbb460" />

3. Deploy. Render's free instance sleeps when idle and wakes on the next visit;
   your data lives in Turso, so nothing is lost across sleeps or redeploys.

### Fly.io alternative (plain SQLite on a volume — needs a card)
See `fly.toml`: `fly launch --no-deploy`, `fly volumes create data --size 1`,
`fly secrets set APP_PASSWORD=... SECRET_KEY=$(openssl rand -hex 32)`, `fly deploy`.
On Fly, leave the Turso vars unset — it uses the local SQLite file on the volume.

## Development

```bash
make install-dev   # runtime + dev tooling (ruff, mypy, hypothesis)
make run           # uvicorn app:app --reload  (defaults APP_PASSWORD/SECRET_KEY)
make test          # test_money.py (unit + property) + test_app.py (integration)
make lint          # ruff check .
make typecheck     # mypy (money/config/auth)
make hooks         # install the pre-commit git hooks
```

**Demo data for screenshots** — `python scripts/seed_demo.py` fills a throwaway `demo.db`
(never your real data or Turso) with two months of expenses across ~10 categories, then run
`env -u TURSO_DATABASE_URL -u TURSO_AUTH_TOKEN APP_PASSWORD=demo DB_PATH=demo.db uvicorn app:app --reload`
to capture the README screens (the `env -u` keeps an exported Turso config from overriding `DB_PATH`).

## Continuous integration

`.github/workflows/ci.yml` runs on every push and PR (with `concurrency` so superseded runs cancel):

- **Tests** — `test_money.py` (pure money math + **Hypothesis** property tests: split always sums,
  paying back the balance settles), `test_app.py` (integration smoke via `TestClient`, offline
  against a throwaway SQLite DB), and `test_handlers.py` (static guard: every inline `on*` handler is
  exposed on `window`).
- **UI E2E** — `test_ui.py` drives a real headless **Playwright** Chromium against a live server and
  clicks every interactive control (category picker, payer switch, add/edit/delete, settle, trends,
  recurring, notes, settings, onboarding, login) — a regression of any inline handler fails the build.
  Gates deploy. Run locally with `make ui-setup && make ui`.
- **Lint & types** — `ruff check .` (`ruff.toml`) and `mypy` over the typed modules (`money/config/auth`).
- **Security** — `pip-audit` (dependency CVE scan) and **gitleaks** (secret scan).
- **API fuzzing** — **schemathesis** hammers the FastAPI OpenAPI schema with generated inputs
  (authenticated). *Advisory* (non-blocking) — it surfaces input-validation/robustness gaps to harden later.
- **Turso smoke** — runs only when `TURSO_DATABASE_URL` / `TURSO_AUTH_TOKEN` repo secrets are set; boots
  against Turso and checks migrate + bootstrap. **Point those secrets at a throwaway test DB, not prod.**
- **Render deploy** — on push to `main` (Render also auto-deploys `main` via its GitHub integration; the
  job additionally hits `RENDER_DEPLOY_HOOK_URL` if that secret is set).

Also: **CodeQL** (`.github/workflows/codeql.yml`) static security analysis, **Dependabot**
(`.github/dependabot.yml`) weekly dependency + Actions updates, **pre-commit** (`.pre-commit-config.yaml`)
local guardrails, and **CodeRabbit** (`.coderabbit.yaml`) automated PR review.

One-time manual setup (repo owner):
1. Install the **CodeRabbit** GitHub app on the repo.
2. (Optional) Add repo **secrets**: `TURSO_DATABASE_URL` + `TURSO_AUTH_TOKEN` (test DB) for the Turso
   smoke, and `RENDER_DEPLOY_HOOK_URL` if you want CI to trigger the Render deploy.

## Notes
- All money is stored as integer **paise** — no floating-point rounding bugs.
- The global ratio is derived from the two incomes; editing incomes only affects
  **future** expenses. Past expenses keep the ratio they were saved with.
