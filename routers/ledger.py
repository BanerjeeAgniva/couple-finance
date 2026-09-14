"""Balance, first-render bootstrap, and settlements."""
from datetime import date

from fastapi import APIRouter, Depends, Request

import config
from auth import require_auth
from db import balance_payload, db, post_due_recurring

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/api/balance")
def balance():
    with db() as c:
        post_due_recurring(c)
        return balance_payload(c)


@router.get("/api/bootstrap")
def bootstrap():
    """One round trip for first render: settings + categories + balance (+ ocr flag)."""
    with db() as c:
        post_due_recurring(c)
        settings = dict(c.execute("SELECT * FROM settings WHERE id=1").fetchone())
        cats = [dict(r) for r in c.execute("SELECT * FROM categories ORDER BY name")]
        bal = balance_payload(c)
    return {"ocr": bool(config.OCR_KEY), "settings": settings, "categories": cats, "balance": bal}


@router.post("/api/settlements")
async def add_settlement(request: Request):
    b = await request.json()
    with db() as c:
        c.execute("""INSERT INTO settlements (date, amount_paise, from_person, to_person, note)
                  VALUES (?,?,?,?,?)""",
                  (b.get("date") or date.today().isoformat(), int(b["amount_paise"]),
                   int(b["from_person"]), int(b["to_person"]), b.get("note", "")))
    return {"ok": True}


@router.get("/api/settlements")
def list_settlements():
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM settlements ORDER BY date DESC, id DESC")]


@router.delete("/api/settlements/{sid}")
def del_settlement(sid: int):
    with db() as c:
        c.execute("DELETE FROM settlements WHERE id=?", (sid,))
    return {"ok": True}
