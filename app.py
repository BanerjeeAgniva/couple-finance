"""Couple Finance — a tiny shared expense tracker for two people.

Single-file FastAPI + SQLite app. Money is stored as integer paise everywhere.
Run: APP_PASSWORD=secret SECRET_KEY=whatever uvicorn app:app --reload
"""
import csv
import hmac
import io
import os
import re
import sqlite3
import urllib.parse
from datetime import date, datetime
from hashlib import sha256
from pathlib import Path

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

DB_PATH = os.environ.get("DB_PATH", "couple_finance.db")
PASSWORD = os.environ.get("APP_PASSWORD", "changeme")
SECRET = os.environ.get("SECRET_KEY", "dev-secret-change-me")
OCR_KEY = os.environ.get("OCR_SPACE_API_KEY", "")
STATIC = Path(__file__).parent / "static"

# Turso (card-free hosted SQLite). Set both env vars in prod; unset locally -> plain sqlite3.
TURSO_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_TOKEN = os.environ.get("TURSO_AUTH_TOKEN", "")

DEFAULT_CATEGORIES = ["Rent", "Groceries", "Eating out", "Utilities",
                      "Transport", "Shopping", "Other"]

app = FastAPI()


@app.middleware("http")
async def _cache_static_fonts(request: Request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/static/fonts/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


# ---- pure money logic (imported by test_money.py) --------------------------

def split(amount_paise: int, r1: int, r2: int) -> tuple[int, int]:
    """Split amount by ratio r1:r2. share1 gets any leftover paisa so the two
    shares always sum back to exactly amount_paise."""
    if r1 + r2 <= 0:
        raise ValueError("ratio must be positive")
    share1 = round(amount_paise * r1 / (r1 + r2))
    # ponytail: derive share2 by subtraction so shares always sum to the total
    share2 = amount_paise - share1
    return share1, share2


def resolve_ratio(row_r1, row_r2, global_r1, global_r2) -> tuple[int, int]:
    """Per-expense override wins over the global ratio when present."""
    if row_r1 is not None and row_r2 is not None:
        return row_r1, row_r2
    return global_r1, global_r2


def compute_balance(expenses, settlements, global_r1, global_r2) -> int:
    """Net paise person 2 owes person 1 (negative = person 1 owes person 2).

    expenses: iterable of (amount_paise, paid_by, override_r1, override_r2)
    settlements: iterable of (amount_paise, from_person, to_person)
    """
    bal = 0  # positive => person 2 owes person 1
    for amount, paid_by, or1, or2 in expenses:
        r1, r2 = resolve_ratio(or1, or2, global_r1, global_r2)
        share1, share2 = split(amount, r1, r2)
        if paid_by == 1:
            bal += amount - share1   # person 2 owes their share to person 1
        else:
            bal -= amount - share2   # person 1 owes their share to person 2
    for amount, frm, to in settlements:
        # a payment from 2 to 1 reduces what 2 owes 1
        bal += amount if frm == 1 else -amount
    return bal


def upi_link(vpa: str, name: str, amount_paise: int, note: str = "Couple Finance") -> str:
    """Build a UPI intent URL that opens GPay/PhonePe/etc. with the payee prefilled."""
    q = urllib.parse.urlencode({
        "pa": vpa, "pn": name, "am": f"{amount_paise / 100:.2f}", "cu": "INR", "tn": note,
    })
    return "upi://pay?" + q


def parse_receipt_total(text: str) -> int | None:
    """Best-effort grand total in paise from OCR'd receipt text.
    Prefer an amount on a line mentioning total/amount/grand; else the largest amount seen."""
    amt_re = re.compile(r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*\.[0-9]{2}|[0-9][0-9,]{2,})", re.I)
    def to_paise(s):
        return round(float(s.replace(",", "")) * 100)
    labelled = []
    for line in text.splitlines():
        if re.search(r"\b(grand\s*total|total|amount|balance|net\s*payable)\b", line, re.I) \
           and not re.search(r"sub\s*total", line, re.I):
            labelled += [to_paise(m) for m in amt_re.findall(line)]
    if labelled:
        return max(labelled)
    allamts = [to_paise(m) for m in amt_re.findall(text)]
    return max(allamts) if allamts else None


def category_monthly(rows, keys):
    """Per-category monthly spend + transaction count over the given month keys.

    rows: iterable of mappings with 'date' (ISO string), 'category', 'amount_paise'.
    keys: ['YYYY-MM', ...] oldest->newest.
    Returns {category: {'count': int, 'series': [paise per key]}}, series aligned to keys, 0-filled.
    """
    idx = {k: i for i, k in enumerate(keys)}
    out: dict[str, dict] = {}
    for r in rows:
        i = idx.get((r["date"] or "")[:7])
        if i is None:
            continue
        cat = r["category"] or "Uncategorised"
        e = out.get(cat) or out.setdefault(cat, {"count": 0, "series": [0] * len(keys)})
        e["count"] += 1
        e["series"][i] += r["amount_paise"]
    return out


# ---- db --------------------------------------------------------------------

class _DictCursor:
    """Wraps a libsql cursor so rows come back as dicts and the cursor iterates,
    matching the sqlite3.Row behaviour the rest of the app expects."""
    def __init__(self, cur):
        self._cur = cur
        self._cols = [d[0] for d in cur.description] if cur.description else []

    def _wrap(self, row):
        return dict(zip(self._cols, row)) if row is not None else None

    def fetchone(self):
        return self._wrap(self._cur.fetchone())

    def fetchall(self):
        return [self._wrap(r) for r in self._cur.fetchall()]

    def __iter__(self):
        return iter(self.fetchall())


class _DictConn:
    """libsql connection wrapper: dict rows + commit-on-`with`-exit."""
    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        # libsql needs a tuple; sqlite3 accepted lists, so callers may pass either
        return _DictCursor(self._c.execute(sql, tuple(params)) if params else self._c.execute(sql))

    def executemany(self, sql, seq):
        self._c.executemany(sql, list(seq)); return self

    def executescript(self, sql):
        self._c.executescript(sql); return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self._c.commit()


def db():
    if TURSO_URL:
        import libsql_experimental as libsql
        # ponytail: pure remote — every query hits Turso (strong read-after-write).
        # Fine for two users; add a connection pool only if latency matters.
        conn = libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN, check_same_thread=False)
        return _DictConn(conn)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id=1),
            name1 TEXT, name2 TEXT,
            income1_paise INTEGER, income2_paise INTEGER);
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, description TEXT, amount_paise INTEGER,
            category_id INTEGER, paid_by INTEGER, paid_to TEXT,
            override_r1 INTEGER, override_r2 INTEGER, created_at TEXT);
        CREATE TABLE IF NOT EXISTS recurring (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            description TEXT, amount_paise INTEGER, category_id INTEGER,
            paid_by INTEGER, paid_to TEXT, day_of_month INTEGER,
            override_r1 INTEGER, override_r2 INTEGER, last_posted_ym TEXT);
        CREATE TABLE IF NOT EXISTS settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT, amount_paise INTEGER, from_person INTEGER,
            to_person INTEGER, note TEXT);
        CREATE TABLE IF NOT EXISTS scratchpad (
            id INTEGER PRIMARY KEY CHECK (id=1), content TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, content TEXT, updated_at TEXT);
        """)
        if not c.execute("SELECT 1 FROM settings WHERE id=1").fetchone():
            c.execute("INSERT INTO settings VALUES (1,?,?,?,?)",
                      ("Person 1", "Person 2", 5000000, 5000000))
        if not c.execute("SELECT 1 FROM categories").fetchone():
            c.executemany("INSERT INTO categories (name) VALUES (?)",
                          [(n,) for n in DEFAULT_CATEGORIES])
        if not c.execute("SELECT 1 FROM scratchpad WHERE id=1").fetchone():
            c.execute("INSERT INTO scratchpad VALUES (1,'',?)", (now(),))


def migrate():
    """Idempotent column adds + one-time data moves (safe on the live Turso DB)."""
    with db() as c:
        for col in ("upi1 TEXT", "upi2 TEXT"):
            try:
                c.execute(f"ALTER TABLE settings ADD COLUMN {col}")
            except Exception:
                pass  # column already exists
        try:
            c.execute("ALTER TABLE notes ADD COLUMN pinned INTEGER DEFAULT 0")
        except Exception:
            pass
        for col in ("avatar1 TEXT", "avatar2 TEXT"):
            try:
                c.execute(f"ALTER TABLE settings ADD COLUMN {col}")
            except Exception:
                pass
        # frequently-used delivery apps as ready-made categories (idempotent; name is UNIQUE)
        for name in ("Amazon", "Blinkit", "Instamart", "Zepto", "Swiggy", "Zomato",
                     "Flipkart", "Pronto", "Furlenco", "Rentomojo", "Snabbit", "UrbanClap",
                     "Rapido", "Uber"):
            c.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (name,))
        # seed the first note from the legacy single scratchpad, once
        if not c.execute("SELECT 1 FROM notes LIMIT 1").fetchone():
            row = c.execute("SELECT content FROM scratchpad WHERE id=1").fetchone()
            if row and (row["content"] or "").strip():
                c.execute("INSERT INTO notes (content, updated_at) VALUES (?,?)",
                          (row["content"], now()))


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def global_ratio(c) -> tuple[int, int]:
    """Global split ratio derived from the two incomes (in paise, kept as ints)."""
    s = c.execute("SELECT income1_paise, income2_paise FROM settings WHERE id=1").fetchone()
    r1, r2 = s["income1_paise"], s["income2_paise"]
    return (r1, r2) if (r1 or 0) + (r2 or 0) > 0 else (1, 1)


# ---- auth ------------------------------------------------------------------

def _token() -> str:
    return hmac.new(SECRET.encode(), b"ok", sha256).hexdigest()


def require_auth(request: Request):
    if not hmac.compare_digest(request.cookies.get("session", ""), _token()):
        raise HTTPException(401, "not logged in")


@app.post("/login")
async def login(request: Request, response: Response):
    body = await request.json()
    if not hmac.compare_digest(str(body.get("password", "")), PASSWORD):
        raise HTTPException(401, "wrong password")
    response.set_cookie("session", _token(), httponly=True, samesite="lax",
                        max_age=60 * 60 * 24 * 365)
    return {"ok": True}


@app.get("/api/me")
def me(request: Request):
    return {"authed": hmac.compare_digest(request.cookies.get("session", ""), _token()),
            "ocr": bool(OCR_KEY)}


# ---- recurring: post any due instances for this month ----------------------

def post_due_recurring(c):
    ym = date.today().strftime("%Y-%m")
    today = date.today().day
    for r in c.execute("SELECT * FROM recurring").fetchall():
        if r["last_posted_ym"] == ym or today < r["day_of_month"]:
            continue
        d = date.today().replace(day=min(r["day_of_month"], 28)).isoformat()
        c.execute("""INSERT INTO expenses (date, description, amount_paise,
                   category_id, paid_by, paid_to, override_r1, override_r2, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                  (d, r["description"], r["amount_paise"], r["category_id"],
                   r["paid_by"], r["paid_to"], r["override_r1"], r["override_r2"], now()))
        c.execute("UPDATE recurring SET last_posted_ym=? WHERE id=?", (ym, r["id"]))


# ---- settings & categories -------------------------------------------------

@app.get("/api/settings", dependencies=[Depends(require_auth)])
def get_settings():
    with db() as c:
        return dict(c.execute("SELECT * FROM settings WHERE id=1").fetchone())


@app.put("/api/settings", dependencies=[Depends(require_auth)])
async def put_settings(request: Request):
    b = await request.json()
    with db() as c:
        c.execute("""UPDATE settings SET name1=?, name2=?, income1_paise=?,
                  income2_paise=?, upi1=?, upi2=? WHERE id=1""",
                  (b["name1"], b["name2"], int(b["income1_paise"]), int(b["income2_paise"]),
                   b.get("upi1", "").strip(), b.get("upi2", "").strip()))
    return {"ok": True}


@app.put("/api/avatar", dependencies=[Depends(require_auth)])
async def set_avatar(request: Request):
    b = await request.json()
    col = "avatar1" if int(b.get("person", 1)) == 1 else "avatar2"
    img = b.get("image") or None            # data URI, or null to clear
    with db() as c:
        c.execute(f"UPDATE settings SET {col}=? WHERE id=1", (img,))
    return {"ok": True}


@app.get("/api/categories", dependencies=[Depends(require_auth)])
def get_categories():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM categories ORDER BY name")]


@app.post("/api/categories", dependencies=[Depends(require_auth)])
async def add_category(request: Request):
    b = await request.json()
    with db() as c:
        c.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (b["name"].strip(),))
    return {"ok": True}


@app.delete("/api/categories/{cid}", dependencies=[Depends(require_auth)])
def del_category(cid: int):
    with db() as c:
        c.execute("DELETE FROM categories WHERE id=?", (cid,))
    return {"ok": True}


# ---- expenses --------------------------------------------------------------

def _expense_rows(c, days=None, month=None):
    q = """SELECT e.*, c.name AS category FROM expenses e
           LEFT JOIN categories c ON c.id = e.category_id"""
    args = []
    if month:
        q += " WHERE substr(e.date,1,7)=?"
        args.append(month)
    elif days:
        q += " WHERE e.date >= date('now', ?)"
        args.append(f"-{int(days)} days")
    q += " ORDER BY e.date DESC, e.id DESC"
    return c.execute(q, args).fetchall()


@app.get("/api/expenses", dependencies=[Depends(require_auth)])
def list_expenses(days: int | None = None, month: str | None = None):
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        out = []
        for r in _expense_rows(c, days, month):
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            d = dict(r)
            d["share1_paise"], d["share2_paise"] = s1, s2
            out.append(d)
        return out


@app.post("/api/expenses", dependencies=[Depends(require_auth)])
async def add_expense(request: Request):
    b = await request.json()
    with db() as c:
        c.execute("""INSERT INTO expenses (date, description, amount_paise, category_id,
                  paid_by, paid_to, override_r1, override_r2, created_at)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
                  (b.get("date") or date.today().isoformat(), b["description"],
                   int(b["amount_paise"]), b.get("category_id"), int(b["paid_by"]),
                   b.get("paid_to", ""), b.get("override_r1"), b.get("override_r2"), now()))
    return {"ok": True}


@app.put("/api/expenses/{eid}", dependencies=[Depends(require_auth)])
async def edit_expense(eid: int, request: Request):
    b = await request.json()
    with db() as c:
        c.execute("""UPDATE expenses SET date=?, description=?, amount_paise=?,
                  category_id=?, paid_by=?, paid_to=?, override_r1=?, override_r2=?
                  WHERE id=?""",
                  (b["date"], b["description"], int(b["amount_paise"]), b.get("category_id"),
                   int(b["paid_by"]), b.get("paid_to", ""), b.get("override_r1"),
                   b.get("override_r2"), eid))
    return {"ok": True}


@app.delete("/api/expenses/{eid}", dependencies=[Depends(require_auth)])
def del_expense(eid: int):
    with db() as c:
        c.execute("DELETE FROM expenses WHERE id=?", (eid,))
    return {"ok": True}


# ---- recurring -------------------------------------------------------------

@app.get("/api/recurring", dependencies=[Depends(require_auth)])
def list_recurring():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM recurring ORDER BY day_of_month")]


@app.post("/api/recurring", dependencies=[Depends(require_auth)])
async def add_recurring(request: Request):
    b = await request.json()
    with db() as c:
        c.execute("""INSERT INTO recurring (description, amount_paise, category_id,
                  paid_by, paid_to, day_of_month, override_r1, override_r2)
                  VALUES (?,?,?,?,?,?,?,?)""",
                  (b["description"], int(b["amount_paise"]), b.get("category_id"),
                   int(b["paid_by"]), b.get("paid_to", ""), int(b["day_of_month"]),
                   b.get("override_r1"), b.get("override_r2")))
    return {"ok": True}


@app.delete("/api/recurring/{rid}", dependencies=[Depends(require_auth)])
def del_recurring(rid: int):
    with db() as c:
        c.execute("DELETE FROM recurring WHERE id=?", (rid,))
    return {"ok": True}


# ---- balance & settlements -------------------------------------------------

def _balance_payload(c):
    """Compute the balance dict on an existing connection (reused by /balance and /bootstrap)."""
    g1, g2 = global_ratio(c)
    exp = [(r["amount_paise"], r["paid_by"], r["override_r1"], r["override_r2"])
           for r in c.execute("SELECT amount_paise, paid_by, override_r1, override_r2 FROM expenses")]
    setl = [(r["amount_paise"], r["from_person"], r["to_person"])
            for r in c.execute("SELECT amount_paise, from_person, to_person FROM settlements")]
    s = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
    bal = compute_balance(exp, setl, g1, g2)
    if bal > 0:
        msg = f"{s['name2']} owes {s['name1']}"
    elif bal < 0:
        msg = f"{s['name1']} owes {s['name2']}"
    else:
        msg = "All settled"
    pay = None
    if bal != 0:
        cred = 1 if bal > 0 else 2           # who is owed → who gets paid
        vpa = (s["upi1"] if cred == 1 else s["upi2"]) or ""
        name = s["name1"] if cred == 1 else s["name2"]
        if vpa:
            pay = {"vpa": vpa, "name": name, "link": upi_link(vpa, name, abs(bal))}
    return {"balance_paise": abs(bal), "message": msg, "raw": bal, "pay": pay}


@app.get("/api/balance", dependencies=[Depends(require_auth)])
def balance():
    with db() as c:
        post_due_recurring(c)
        return _balance_payload(c)


@app.get("/api/bootstrap", dependencies=[Depends(require_auth)])
def bootstrap():
    """One round trip for first render: settings + categories + balance (+ ocr flag)."""
    with db() as c:
        post_due_recurring(c)
        settings = dict(c.execute("SELECT * FROM settings WHERE id=1").fetchone())
        cats = [dict(r) for r in c.execute("SELECT * FROM categories ORDER BY name")]
        bal = _balance_payload(c)
    return {"ocr": bool(OCR_KEY), "settings": settings, "categories": cats, "balance": bal}


@app.post("/api/settlements", dependencies=[Depends(require_auth)])
async def add_settlement(request: Request):
    b = await request.json()
    with db() as c:
        c.execute("""INSERT INTO settlements (date, amount_paise, from_person, to_person, note)
                  VALUES (?,?,?,?,?)""",
                  (b.get("date") or date.today().isoformat(), int(b["amount_paise"]),
                   int(b["from_person"]), int(b["to_person"]), b.get("note", "")))
    return {"ok": True}


@app.get("/api/settlements", dependencies=[Depends(require_auth)])
def list_settlements():
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM settlements ORDER BY date DESC, id DESC")]


@app.delete("/api/settlements/{sid}", dependencies=[Depends(require_auth)])
def del_settlement(sid: int):
    with db() as c:
        c.execute("DELETE FROM settlements WHERE id=?", (sid,))
    return {"ok": True}


# ---- summary (monthly totals) ---------------------------------------------

@app.get("/api/summary", dependencies=[Depends(require_auth)])
def summary(month: str | None = None):
    month = month or date.today().strftime("%Y-%m")
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        total = share1 = share2 = 0
        by_cat: dict[str, int] = {}
        for r in _expense_rows(c, month=month):
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            total += r["amount_paise"]; share1 += s1; share2 += s2
            cat = r["category"] or "Uncategorised"
            by_cat[cat] = by_cat.get(cat, 0) + r["amount_paise"]
        s = c.execute("SELECT name1, name2 FROM settings WHERE id=1").fetchone()
        return {"month": month, "total_paise": total,
                "share1_paise": share1, "share2_paise": share2,
                "name1": s["name1"], "name2": s["name2"],
                "by_category": [{"category": k, "amount_paise": v}
                                for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]}


# ---- activity feed (expenses + settlements merged) -------------------------

@app.get("/api/activity", dependencies=[Depends(require_auth)])
def activity(days: int = 90):
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        items = []
        for r in _expense_rows(c, days=days):
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            d = dict(r); d["type"] = "expense"
            d["share1_paise"], d["share2_paise"] = s1, s2
            items.append(d)
        for r in c.execute("SELECT * FROM settlements WHERE date >= date('now', ?) ORDER BY date DESC, id DESC",
                           (f"-{int(days)} days",)):
            d = dict(r); d["type"] = "settlement"
            items.append(d)
        items.sort(key=lambda x: (x["date"], x.get("created_at") or "", x["id"]), reverse=True)
        return items


# ---- analytics (multi-month trends) ----------------------------------------

@app.get("/api/analytics", dependencies=[Depends(require_auth)])
def analytics(months: int = 6):
    months = max(1, min(months, 24))
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        y, m, keys = date.today().year, date.today().month, []
        for _ in range(months):
            keys.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        keys = list(reversed(keys))
        per = {k: {"month": k, "total_paise": 0, "share1_paise": 0, "share2_paise": 0} for k in keys}
        by_cat: dict[str, int] = {}
        rows = _expense_rows(c)
        for r in rows:
            k = (r["date"] or "")[:7]
            if k not in per:
                continue
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            per[k]["total_paise"] += r["amount_paise"]
            per[k]["share1_paise"] += s1
            per[k]["share2_paise"] += s2
            cat = r["category"] or "Uncategorised"
            by_cat[cat] = by_cat.get(cat, 0) + r["amount_paise"]
        hist = category_monthly(rows, keys)   # per-category monthly series + count, aligned to keys
        s = c.execute("SELECT name1, name2 FROM settings WHERE id=1").fetchone()
        return {"months": [per[k] for k in keys], "name1": s["name1"], "name2": s["name2"],
                "by_category": [{"category": k, "amount_paise": v,
                                 "count": hist.get(k, {}).get("count", 0),
                                 "series": hist.get(k, {}).get("series", [0] * len(keys))}
                                for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]}


# ---- receipt OCR (OCR.space) -----------------------------------------------

@app.post("/api/ocr", dependencies=[Depends(require_auth)])
async def ocr(image: UploadFile = File(...)):
    if not OCR_KEY:
        raise HTTPException(400, "OCR is not configured on the server")
    import httpx
    data = await image.read()
    files = {"file": (image.filename or "receipt.jpg", data, image.content_type or "image/jpeg")}
    form = {"apikey": OCR_KEY, "OCREngine": "2", "isTable": "true", "scale": "true"}
    try:
        async with httpx.AsyncClient(timeout=40) as client:
            resp = await client.post("https://api.ocr.space/parse/image", data=form, files=files)
        j = resp.json()
    except Exception:
        raise HTTPException(502, "Could not reach the OCR service")
    if j.get("IsErroredOnProcessing"):
        raise HTTPException(502, (j.get("ErrorMessage") or ["OCR failed"])[0])
    text = "\n".join(p.get("ParsedText", "") for p in (j.get("ParsedResults") or []))
    merchant = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return {"amount_paise": parse_receipt_total(text), "merchant": merchant[:40]}


# ---- notes -----------------------------------------------------------------

@app.get("/api/notes", dependencies=[Depends(require_auth)])
def list_notes():
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, content, updated_at, COALESCE(pinned,0) AS pinned FROM notes "
            "ORDER BY pinned DESC, updated_at DESC, id DESC")]


@app.post("/api/notes", dependencies=[Depends(require_auth)])
def add_note():
    with db() as c:
        c.execute("INSERT INTO notes (content, updated_at) VALUES ('', ?)", (now(),))
        return {"id": c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]}


@app.put("/api/notes/{nid}", dependencies=[Depends(require_auth)])
async def edit_note(nid: int, request: Request):
    b = await request.json()
    with db() as c:
        if "pinned" in b and "content" not in b:      # pin toggle only, don't bump updated_at
            c.execute("UPDATE notes SET pinned=? WHERE id=?", (1 if b["pinned"] else 0, nid))
        else:
            c.execute("UPDATE notes SET content=?, updated_at=? WHERE id=?",
                      (b.get("content", ""), now(), nid))
            if "pinned" in b:
                c.execute("UPDATE notes SET pinned=? WHERE id=?", (1 if b["pinned"] else 0, nid))
    return {"ok": True}


@app.delete("/api/notes/{nid}", dependencies=[Depends(require_auth)])
def del_note(nid: int):
    with db() as c:
        c.execute("DELETE FROM notes WHERE id=?", (nid,))
    return {"ok": True}


# ---- export ----------------------------------------------------------------

@app.get("/api/export", dependencies=[Depends(require_auth)])
def export(days: int = 30, settlements: int = 0):
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        s = c.execute("SELECT name1, name2 FROM settings WHERE id=1").fetchone()
        buf = io.StringIO()
        w = csv.writer(buf)
        head = ["date", "description", "category", "amount_rs", "paid_by",
                "paid_to", f"{s['name1']}_share_rs", f"{s['name2']}_share_rs"]
        if settlements:
            head = ["type"] + head
        w.writerow(head)
        rowdays = None if days <= 0 else days      # days<=0 => all time
        def row(vals):
            w.writerow((["expense"] + vals) if settlements else vals)
        for r in _expense_rows(c, days=rowdays):
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            payer = s["name1"] if r["paid_by"] == 1 else s["name2"]
            row([r["date"], r["description"], r["category"] or "",
                 f"{r['amount_paise']/100:.2f}", payer, r["paid_to"] or "",
                 f"{s1/100:.2f}", f"{s2/100:.2f}"])
        if settlements:
            q = "SELECT * FROM settlements"
            args = []
            if rowdays:
                q += " WHERE date >= date('now', ?)"; args.append(f"-{rowdays} days")
            q += " ORDER BY date"
            for r in c.execute(q, args):
                frm = s["name1"] if r["from_person"] == 1 else s["name2"]
                to = s["name1"] if r["to_person"] == 1 else s["name2"]
                w.writerow(["settlement", r["date"], f"{frm} paid {to}", "", f"{r['amount_paise']/100:.2f}",
                            frm, to, "", ""])
        buf.seek(0)
        fname = f"couple_finance_{'all' if days <= 0 else 'last_' + str(days) + '_days'}.csv"
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{fname}"'})


# ---- static frontend -------------------------------------------------------

@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")

init_db()
migrate()
