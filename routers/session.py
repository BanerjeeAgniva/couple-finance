"""Login and session-status routes (the only unauthenticated endpoints)."""
import hmac

from fastapi import APIRouter, HTTPException, Request, Response

import config
from auth import token

router = APIRouter()


@router.post("/login")
async def login(request: Request, response: Response):
    body = await request.json()
    if not hmac.compare_digest(str(body.get("password", "")), config.PASSWORD):
        raise HTTPException(401, "wrong password")
    response.set_cookie("session", token(), httponly=True, samesite="lax",
                        max_age=60 * 60 * 24 * 365)
    return {"ok": True}


@router.get("/api/me")
def me(request: Request):
    return {"authed": hmac.compare_digest(request.cookies.get("session", ""), token()),
            "ocr": bool(config.OCR_KEY)}
