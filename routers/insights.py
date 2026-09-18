"""Read-only analytics: monthly summary, merged activity feed, multi-month trends, insights."""
from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Depends

from auth import require_auth
from db import (
    analytics_data, balance_payload, db, expense_rows, global_ratio,
    post_due_recurring, recurring_candidates, weeks_since_last_settlement,
)
from insights_engine import build_insights
from money import resolve_ratio, split

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/api/summary")
def summary(month: str | None = None):
    month = month or date.today().strftime("%Y-%m")
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        total = share1 = share2 = 0
        by_cat: dict[str, int] = {}
        for r in expense_rows(c, month=month):
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            total += r["amount_paise"]; share1 += s1; share2 += s2
            cat = r["category"] or "Uncategorised"
            by_cat[cat] = by_cat.get(cat, 0) + r["amount_paise"]
        s = c.execute("SELECT name1, name2 FROM settings WHERE id=1").fetchone()
        return {"month": month, "total_paise": total,
                "share1_paise": share1, "share2_paise": share2,
                "name1": s["name1"], "name2": s["name2"],
                "by_category": [{"category": k, "amount_paise": v}
                                for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]}


@router.get("/api/activity")
def activity(days: int = 90):
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        items = []
        for r in expense_rows(c, days=days):
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            d = dict(r); d["type"] = "expense"
            d["share1_paise"], d["share2_paise"] = s1, s2
            items.append(d)
        for r in c.execute("SELECT * FROM settlements WHERE date >= date('now', ?) ORDER BY date DESC, id DESC",
                           (f"-{int(days)} days",)):
            d = dict(r); d["type"] = "settlement"
            items.append(d)
        items.sort(key=lambda x: (x["date"], x.get("created_at") or "", x["id"]), reverse=True)
        return items


@router.get("/api/analytics")
def analytics(months: int = 6):
    with db() as c:
        post_due_recurring(c)          # the /api/analytics route owns recurring posting
        return analytics_data(c, months)


@router.get("/api/insights")
def insights():
    """Ranked, couple-friendly insight cards — pure math on data the app already has.
    No LLM, no network, and read-only (no writes), so it's safe to run alongside
    /api/analytics; financial data never leaves the server."""
    today = date.today()
    with db() as c:
        a = analytics_data(c, 6)       # read-only; recurring already posted by /api/analytics
        data = {
            "keys": [m["month"] for m in a["months"]],
            "month_totals": [m["total_paise"] for m in a["months"]],
            "categories": [{"category": x["category"], "series": x["series"]} for x in a["by_category"]],
            "current_day": today.day,
            "days_in_month": monthrange(today.year, today.month)[1],
            "balance_raw": balance_payload(c)["raw"],
            "name1": a["name1"], "name2": a["name2"],
            "weeks_since_settle": weeks_since_last_settlement(c),
            "recurring_candidates": recurring_candidates(c),
        }
    return {"insights": build_insights(data)}
