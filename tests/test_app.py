"""Integration smoke for the composed app. `python test_app.py`.

Runs offline against a throwaway local SQLite DB (Turso disabled) so the real
database is never touched. Proves the routers, auth, and DB layer wire together.
"""
import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.gettempdir(), "couple_ci_test.db")
os.environ.setdefault("SECRET_KEY", "ci-secret")
os.environ.setdefault("APP_PASSWORD", "ci-pass")
os.environ.pop("TURSO_DATABASE_URL", None)   # force local sqlite, never hit Turso
try:
    os.remove(os.environ["DB_PATH"])
except OSError:
    pass

from fastapi.testclient import TestClient  # noqa: E402
import app  # noqa: E402

authed = TestClient(app.app)
authed.post("/login", json={"password": os.environ["APP_PASSWORD"]})


def test_requires_auth():
    fresh = TestClient(app.app)  # no session cookie
    assert fresh.get("/api/me").json()["authed"] is False
    assert fresh.get("/api/settings").status_code == 401


def test_wrong_password_rejected():
    assert TestClient(app.app).post("/login", json={"password": "nope"}).status_code == 401


def test_bootstrap_and_analytics():
    b = authed.get("/api/bootstrap").json()
    assert {"settings", "categories", "balance"} <= b.keys(), b
    a = authed.get("/api/analytics?months=6").json()
    assert "months" in a and "by_category" in a, a
    assert "mom_pct" in a and "top_merchant" in a, a       # trend stats
    assert "balance_paise" in authed.get("/api/balance").json()


def test_expense_note_roundtrip():
    authed.post("/api/expenses",
                json={"description": "Dinner", "amount_paise": 8000, "paid_by": 1,
                      "note": "anniversary treat"})
    assert any(r.get("note") == "anniversary treat" for r in authed.get("/api/expenses").json())
    assert any(r.get("note") == "anniversary treat"
               for r in authed.get("/api/activity?days=0").json() if r.get("type") == "expense")


def test_note_preserved_when_put_omits_it():
    authed.post("/api/expenses",
                json={"description": "Cab", "amount_paise": 3000, "paid_by": 1, "note": "keep me"})
    eid = max(e["id"] for e in authed.get("/api/expenses").json() if e["description"] == "Cab")
    base = {"date": "2026-09-10", "description": "Cab", "amount_paise": 3000, "paid_by": 1}
    # a PUT that omits the note key must keep the existing note
    authed.put(f"/api/expenses/{eid}", json=base)
    assert next(e for e in authed.get("/api/expenses").json() if e["id"] == eid)["note"] == "keep me"
    # ...but an explicit empty note clears it
    authed.put(f"/api/expenses/{eid}", json={**base, "note": ""})
    assert next(e for e in authed.get("/api/expenses").json() if e["id"] == eid)["note"] in (None, "")


def test_expense_write_and_readback():
    assert authed.post("/api/expenses",
                       json={"description": "Test", "amount_paise": 10000, "paid_by": 1}
                       ).json() == {"ok": True}
    assert any(r["description"] == "Test" for r in authed.get("/api/expenses").json())


def test_activity_all_time():
    # days=0 means no date window — an old-dated expense must still appear
    authed.post("/api/expenses",
                json={"description": "OldOne", "amount_paise": 5000, "paid_by": 1, "date": "2020-01-01"})
    feed = authed.get("/api/activity?days=0").json()
    assert any(r.get("description") == "OldOne" for r in feed if r.get("type") == "expense"), feed
    # the default 90-day window must exclude it
    recent = authed.get("/api/activity?days=90").json()
    assert not any(r.get("description") == "OldOne" for r in recent if r.get("type") == "expense")


def test_category_budget():
    authed.post("/api/categories", json={"name": "Budgeted"})
    cid = next(c["id"] for c in authed.get("/api/categories").json() if c["name"] == "Budgeted")
    # set a cap
    assert authed.put(f"/api/categories/{cid}", json={"budget_paise": 500000}).json() == {"ok": True}
    cats = {c["id"]: c for c in authed.get("/api/categories").json()}
    assert cats[cid]["budget_paise"] == 500000
    # empty clears it back to NULL
    authed.put(f"/api/categories/{cid}", json={"budget_paise": ""})
    cats = {c["id"]: c for c in authed.get("/api/categories").json()}
    assert cats[cid]["budget_paise"] is None


def _set_income(i1, i2):
    s = authed.get("/api/settings").json()
    return authed.put("/api/settings", json={
        "name1": s["name1"], "name2": s["name2"],
        "income1_paise": i1, "income2_paise": i2,
        "upi1": s.get("upi1") or "", "upi2": s.get("upi2") or ""})


def test_income_split_frozen_on_income_change():
    # a "By income" expense snapshots the current ratio and must survive an income change
    authed.post("/api/expenses",
                json={"description": "FreezeMe", "amount_paise": 100000, "paid_by": 1,
                      "split_mode": "ratio"})
    row = next(e for e in authed.get("/api/expenses").json() if e["description"] == "FreezeMe")
    assert row["split_mode"] == "ratio"
    assert row["override_r1"] is not None and row["override_r2"] is not None   # ratio was snapshotted
    frozen = (row["share1_paise"], row["share2_paise"])
    bal_before = authed.get("/api/balance").json()["raw"]
    # skew income hard; the old expense's split and the balance must not move
    _set_income(9000000, 1000000)
    after = next(e for e in authed.get("/api/expenses").json() if e["description"] == "FreezeMe")
    assert (after["share1_paise"], after["share2_paise"]) == frozen
    assert authed.get("/api/balance").json()["raw"] == bal_before
    # ...but a NEW income-split expense uses the NEW 90:10 ratio
    authed.post("/api/expenses",
                json={"description": "AfterRaise", "amount_paise": 100000, "paid_by": 1,
                      "split_mode": "ratio"})
    fresh = next(e for e in authed.get("/api/expenses").json() if e["description"] == "AfterRaise")
    assert fresh["share1_paise"] == 90000


def test_income_change_logged_and_in_feed():
    before = len(authed.get("/api/income-history").json())
    cur = authed.get("/api/settings").json()
    _set_income(cur["income1_paise"] + 500000, cur["income2_paise"])
    hist = authed.get("/api/income-history").json()
    assert len(hist) == before + 1
    assert hist[0]["new_income1_paise"] == cur["income1_paise"] + 500000
    assert any(it.get("type") == "income" for it in authed.get("/api/activity?days=0").json())


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"ok  {name}")
    print("all passed")
