"""Recurring (auto-posting monthly) expenses."""
from fastapi import APIRouter, Depends, Request

from auth import require_auth
from db import db

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/api/recurring")
def list_recurring():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM recurring ORDER BY day_of_month")]


@router.post("/api/recurring")
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


@router.delete("/api/recurring/{rid}")
def del_recurring(rid: int):
    with db() as c:
        c.execute("DELETE FROM recurring WHERE id=?", (rid,))
    return {"ok": True}
