"""Settings, avatars, and category management."""
from fastapi import APIRouter, Depends, Request

from auth import require_auth
from db import db

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/api/settings")
def get_settings():
    with db() as c:
        return dict(c.execute("SELECT * FROM settings WHERE id=1").fetchone())


@router.put("/api/settings")
async def put_settings(request: Request):
    b = await request.json()
    with db() as c:
        c.execute("""UPDATE settings SET name1=?, name2=?, income1_paise=?,
                  income2_paise=?, upi1=?, upi2=? WHERE id=1""",
                  (b["name1"], b["name2"], int(b["income1_paise"]), int(b["income2_paise"]),
                   b.get("upi1", "").strip(), b.get("upi2", "").strip()))
    return {"ok": True}


@router.put("/api/avatar")
async def set_avatar(request: Request):
    b = await request.json()
    col = "avatar1" if int(b.get("person", 1)) == 1 else "avatar2"
    img = b.get("image") or None            # data URI, or null to clear
    with db() as c:
        c.execute(f"UPDATE settings SET {col}=? WHERE id=1", (img,))
    return {"ok": True}


@router.get("/api/categories")
def get_categories():
    with db() as c:
        return [dict(r) for r in c.execute("SELECT * FROM categories ORDER BY name")]


@router.post("/api/categories")
async def add_category(request: Request):
    b = await request.json()
    with db() as c:
        c.execute("INSERT OR IGNORE INTO categories (name) VALUES (?)", (b["name"].strip(),))
    return {"ok": True}


@router.put("/api/categories/{cid}")
async def set_category_budget(cid: int, request: Request):
    b = await request.json()
    raw = b.get("budget_paise")
    cap = int(raw) if raw not in (None, "", 0, "0") else None  # 0/empty clears the cap
    if cap is not None and cap < 0:
        cap = None
    with db() as c:
        c.execute("UPDATE categories SET budget_paise=? WHERE id=?", (cap, cid))
    return {"ok": True}


@router.delete("/api/categories/{cid}")
def del_category(cid: int):
    with db() as c:
        c.execute("DELETE FROM categories WHERE id=?", (cid,))
    return {"ok": True}
