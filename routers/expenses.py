"""Expense CRUD."""
from datetime import date

from fastapi import APIRouter, Depends, Request

from auth import require_auth
from db import db, expense_rows, global_ratio, now, post_due_recurring
from money import resolve_ratio, split

router = APIRouter(dependencies=[Depends(require_auth)])


def _split_snapshot(c, b):
    """Resolve the (split_mode, override_r1, override_r2) to persist for an expense.

    'ratio' (split by income) snapshots the CURRENT income ratio into the overrides so the
    split is frozen — a later income change never re-splits this row. 'half' stores 1:1,
    'custom' stores the posted values. Mode falls back to the overrides for older clients:
    no overrides → income ('ratio'); 1:1 → 'half'; else 'custom'."""
    or1, or2 = b.get("override_r1"), b.get("override_r2")
    mode = b.get("split_mode")
    if not mode:
        mode = "ratio" if or1 is None or or2 is None else ("half" if or1 == 1 and or2 == 1 else "custom")
    if mode == "ratio":
        or1, or2 = global_ratio(c)
    elif mode == "half":
        or1, or2 = 1, 1
    return mode, or1, or2


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
        mode, or1, or2 = _split_snapshot(c, b)
        c.execute("""INSERT INTO expenses (date, description, amount_paise, category_id,
                  paid_by, paid_to, override_r1, override_r2, split_mode, note, created_at)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                  (b.get("date") or date.today().isoformat(), b["description"],
                   int(b["amount_paise"]), b.get("category_id"), int(b["paid_by"]),
                   b.get("paid_to", ""), or1, or2, mode,
                   b.get("note", ""), now()))
    return {"ok": True}


@router.put("/api/expenses/{eid}")
async def edit_expense(eid: int, request: Request):
    b = await request.json()
    with db() as c:
        # re-snapshot the split on save: picking "By income" refreshes to today's ratio,
        # while 'half'/'custom' store their explicit ratio.
        mode, or1, or2 = _split_snapshot(c, b)
        # note is only overwritten when the key is present, so a PUT that omits it keeps the
        # existing note (sending "" still clears it explicitly)
        c.execute("""UPDATE expenses SET date=?, description=?, amount_paise=?,
                  category_id=?, paid_by=?, paid_to=?, override_r1=?, override_r2=?, split_mode=?,
                  note=CASE WHEN ? THEN ? ELSE note END
                  WHERE id=?""",
                  (b["date"], b["description"], int(b["amount_paise"]), b.get("category_id"),
                   int(b["paid_by"]), b.get("paid_to", ""), or1, or2, mode,
                   "note" in b, b.get("note", ""), eid))
    return {"ok": True}


@router.delete("/api/expenses/{eid}")
def del_expense(eid: int):
    with db() as c:
        c.execute("DELETE FROM expenses WHERE id=?", (eid,))
    return {"ok": True}
