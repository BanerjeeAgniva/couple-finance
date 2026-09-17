"""Data layer: connection (sqlite3 locally / Turso in prod), schema, migrations,
and connection-taking query helpers. Depends on config and the pure money module.
"""
import sqlite3
from datetime import date, datetime

import config
from money import compute_balance, upi_link


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
    if config.TURSO_URL:
        import libsql_experimental as libsql
        # ponytail: pure remote — every query hits Turso (strong read-after-write).
        # Fine for two users; add a connection pool only if latency matters.
        conn = libsql.connect(config.TURSO_URL, auth_token=config.TURSO_TOKEN, check_same_thread=False)
        return _DictConn(conn)
    conn = sqlite3.connect(config.DB_PATH)
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
                          [(n,) for n in config.DEFAULT_CATEGORIES])
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


def expense_rows(c, days=None, month=None):
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


def balance_payload(c):
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
