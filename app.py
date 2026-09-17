"""Couple Finance — a tiny shared expense tracker for two people.

Composition root: builds the FastAPI app, wires the resource routers, serves the
static frontend, and provisions the database at import. Behaviour lives in the
focused modules — config, money (pure domain), db, auth, and routers/*.

Run: APP_PASSWORD=secret SECRET_KEY=whatever uvicorn app:app --reload
"""
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from db import init_db, migrate
from routers import (
    expenses, export, insights, ledger, notes, ocr, recurring, session, settings,
)

# Re-exported so `from app import ...` keeps working (test_money.py and any external callers).
from money import (  # noqa: F401
    category_monthly, compute_balance, parse_receipt_total, resolve_ratio, split, upi_link,
)

app = FastAPI()


@app.middleware("http")
async def _cache_static_fonts(request: Request, call_next):
    resp = await call_next(request)
    if request.url.path.startswith("/static/fonts/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    return resp


for _router in (session, settings, expenses, recurring, ledger, insights, ocr, notes, export):
    app.include_router(_router.router)


@app.get("/")
def index():
    return FileResponse(config.STATIC / "index.html")


app.mount("/static", StaticFiles(directory=config.STATIC), name="static")

# Provision a fresh Turso/SQLite DB (idempotent) before the first request.
init_db()
migrate()
