# Couple Finance

A tiny shared expense tracker for two people. Log expenses, auto-split by income
ratio, and track who owes whom. Shared password, no per-user accounts.

## Features
- **Income-ratio split** — set both incomes once; every expense splits automatically.
- **Who paid → who owes** — running settle-up balance + "mark as settled".
- **Per-expense override** — change the split for one expense without touching the global ratio.
- **Recurring** — rent/wifi/etc. auto-posted each month.
- **Monthly totals** — total, per-person share, per-category breakdown.
- **Categories, paid-to (merchant), scratchpad notes.**
- **CSV export** — last N days with each person's share.

## Run locally
```bash
pip install -r requirements.txt
export APP_PASSWORD=yourpassword
export SECRET_KEY=$(openssl rand -hex 32)
uvicorn app:app --reload
# open http://localhost:8000
python test_money.py    # money-math checks
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

## Notes
- All money is stored as integer **paise** — no floating-point rounding bugs.
- The global ratio is derived from the two incomes; editing incomes only affects
  **future** expenses. Past expenses keep the ratio they were saved with.
