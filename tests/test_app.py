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
    assert "balance_paise" in authed.get("/api/balance").json()


def test_expense_write_and_readback():
    assert authed.post("/api/expenses",
                       json={"description": "Test", "amount_paise": 10000, "paid_by": 1}
                       ).json() == {"ok": True}
    assert any(r["description"] == "Test" for r in authed.get("/api/expenses").json())


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


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"ok  {name}")
    print("all passed")
