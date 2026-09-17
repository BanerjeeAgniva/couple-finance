"""CI smoke against Turso: boot the app with the configured TURSO_* env and confirm
it can migrate + serve. Point TURSO_DATABASE_URL at a THROWAWAY test database, not prod.

Only invoked by CI when the TURSO_* secrets are set (see .github/workflows/ci.yml).
"""
import os

from fastapi.testclient import TestClient

import app  # importing runs init_db()/migrate() against the configured DB (idempotent)

c = TestClient(app.app)
assert c.post("/login", json={"password": os.environ["APP_PASSWORD"]}).json() == {"ok": True}
b = c.get("/api/bootstrap").json()
assert {"settings", "categories", "balance"} <= b.keys(), b
print("Turso smoke OK — migrate + bootstrap succeeded against Turso")
