"""Shared notes (with pin + checklist support on the frontend)."""
from fastapi import APIRouter, Depends, Request

from auth import require_auth
from db import db, now

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/api/notes")
def list_notes():
    with db() as c:
        return [dict(r) for r in c.execute(
            "SELECT id, content, updated_at, COALESCE(pinned,0) AS pinned FROM notes "
            "ORDER BY pinned DESC, updated_at DESC, id DESC")]


@router.post("/api/notes")
def add_note():
    with db() as c:
        c.execute("INSERT INTO notes (content, updated_at) VALUES ('', ?)", (now(),))
        return {"id": c.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]}


@router.put("/api/notes/{nid}")
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


@router.delete("/api/notes/{nid}")
def del_note(nid: int):
    with db() as c:
        c.execute("DELETE FROM notes WHERE id=?", (nid,))
    return {"ok": True}
