"""Expense CRUD."""
from datetime import date

from fastapi import APIRouter, Depends, Request

from auth import require_auth
from db import db, expense_rows, global_ratio, now, post_due_recurring
from money import resolve_ratio, split

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/api/expenses")
def list_expenses(days: int | None = None, month: str | None = None):
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        out = []
        for r in expense_rows(c, days, month):
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            d = dict(r)
            d["share1_paise"], d["share2_paise"] = s1, s2
            out.append(d)
        return out


@router.post("/api/expenses")
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


@router.put("/api/expenses/{eid}")
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


@router.delete("/api/expenses/{eid}")
def del_expense(eid: int):
    with db() as c:
        c.execute("DELETE FROM expenses WHERE id=?", (eid,))
    return {"ok": True}
