#!/usr/bin/env python3
"""Seed an isolated local SQLite DB with demo data for README screenshots.

Never touches your real data or Turso: it forces DB_PATH to a throwaway file
(default demo.db) and unsets the Turso env vars before importing the app's db
layer, so the schema always matches production via db.init_db()/migrate().

Usage:
    python scripts/seed_demo.py                 # writes ./demo.db (overwrites)
    DB_PATH=/tmp/shots.db python scripts/seed_demo.py
    # then run the app against the same DB and screenshot:
    APP_PASSWORD=demo DB_PATH=demo.db uvicorn app:app --reload
"""
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Isolate BEFORE importing config/db: own file, plain sqlite3 (no Turso).
os.environ.setdefault("DB_PATH", "demo.db")
os.environ.pop("TURSO_DATABASE_URL", None)
os.environ.pop("TURSO_AUTH_TOKEN", None)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from anywhere
import config  # noqa: E402
import db  # noqa: E402

# Two people with unequal incomes — mirrors the README's 60/40 story.
NAME1, NAME2 = "Arjun", "Nandini"
INCOME1, INCOME2 = 90_000_00, 60_000_00  # paise
UPI1, UPI2 = "arjun@okhdfc", "nandini@okaxis"

# Curated ~2 months of expenses: (days_ago, description, rupees, category, paid_by).
# Enough per category that the activity filter shows a meaningful count + total.
EXPENSES = [
    (2, "Weekly groceries", 2340, "Groceries", 1),
    (9, "Monthly stock-up", 4180, "Groceries", 2),
    (16, "Veggies & fruit", 890, "Groceries", 1),
    (23, "Groceries", 2610, "Groceries", 2),
    (44, "Big Basket order", 3120, "Groceries", 1),
    (1, "Dinner delivery", 640, "Swiggy", 2),
    (6, "Late-night biryani", 520, "Swiggy", 1),
    (13, "Weekend lunch", 780, "Swiggy", 2),
    (28, "Office snacks", 410, "Swiggy", 1),
    (3, "Pizza night", 950, "Zomato", 1),
    (17, "Brunch", 1120, "Zomato", 2),
    (34, "Team treat", 1680, "Zomato", 1),
    (4, "Phone charger + cable", 1290, "Amazon", 2),
    (12, "Kitchen rack", 2450, "Amazon", 1),
    (30, "Books", 860, "Amazon", 2),
    (48, "Bedsheet set", 1990, "Amazon", 1),
    (5, "Milk & eggs", 210, "Blinkit", 1),
    (11, "Instant delivery", 340, "Blinkit", 2),
    (20, "Snacks run", 280, "Blinkit", 1),
    (7, "Cab to airport", 720, "Uber", 2),
    (25, "Late cab home", 310, "Uber", 1),
    (8, "Bike ride", 90, "Rapido", 2),
    (22, "Quick ride", 110, "Rapido", 1),
    (10, "Electricity bill", 1840, "Utilities", 2),
    (10, "Broadband", 999, "Utilities", 1),
    (15, "Anniversary dinner", 3200, "Eating out", 1),
    (38, "Cafe date", 640, "Eating out", 2),
    (1, "Rent", 42000, "Rent", 1),   # big, split by ratio — dominates the balance
    (31, "Rent", 42000, "Rent", 2),
]


def cat_ids(c):
    return {r["name"]: r["id"] for r in c.execute("SELECT id, name FROM categories")}


def main():
    path = Path(config.DB_PATH)
    if path.exists():
        path.unlink()  # fresh, reproducible screenshots every run
    db.init_db()
    db.migrate()  # adds upi/avatar cols + the delivery-app categories used below
    with db.db() as c:
        c.execute(
            "UPDATE settings SET name1=?, name2=?, income1_paise=?, income2_paise=?, upi1=?, upi2=? WHERE id=1",
            (NAME1, NAME2, INCOME1, INCOME2, UPI1, UPI2),
        )
        ids = cat_ids(c)
        now = datetime.now().isoformat(timespec="seconds")
        for days_ago, desc, rupees, cat, paid_by in EXPENSES:
            cid = ids.get(cat)
            if cid is None:  # category not seeded — fail loud rather than silently skip
                raise SystemExit(f"Unknown category {cat!r}; add it to db.migrate() or DEFAULT_CATEGORIES")
            d = (date.today() - timedelta(days=days_ago)).isoformat()
            c.execute(
                """INSERT INTO expenses (date, description, amount_paise, category_id,
                   paid_by, paid_to, override_r1, override_r2, created_at)
                   VALUES (?,?,?,?,?,NULL,NULL,NULL,?)""",
                (d, desc, rupees * 100, cid, paid_by, now),
            )
    total = sum(r for _, _, r, _, _ in EXPENSES)
    print(f"Seeded {len(EXPENSES)} expenses (₹{total:,}) across "
          f"{len({e[3] for e in EXPENSES})} categories into {path}")
    print(f"Run:  APP_PASSWORD=demo DB_PATH={path} uvicorn app:app --reload")


if __name__ == "__main__":
    main()
