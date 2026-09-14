"""Authentication mechanism: a single shared password proven by an HMAC-signed
session cookie. `require_auth` is the FastAPI dependency every protected router uses.
"""
import hmac
from hashlib import sha256

from fastapi import HTTPException, Request

import config


def token() -> str:
    return hmac.new(config.SECRET.encode(), b"ok", sha256).hexdigest()


def require_auth(request: Request):
    if not hmac.compare_digest(request.cookies.get("session", ""), token()):
        raise HTTPException(401, "not logged in")
