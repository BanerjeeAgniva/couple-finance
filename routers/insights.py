"""Read-only analytics: monthly summary, merged activity feed, multi-month trends, insights."""
from calendar import monthrange
from datetime import date

from fastapi import APIRouter, Depends

from auth import require_auth
from db import balance_payload, db, expense_rows, global_ratio, post_due_recurring
from insights_engine import build_insights
from money import category_monthly, resolve_ratio, split

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
    months = max(1, min(months, 24))
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        y, m, keys = date.today().year, date.today().month, []
        for _ in range(months):
            keys.append(f"{y:04d}-{m:02d}")
            m -= 1
            if m == 0:
                m, y = 12, y - 1
        keys = list(reversed(keys))
        per = {k: {"month": k, "total_paise": 0, "share1_paise": 0, "share2_paise": 0} for k in keys}
        by_cat: dict[str, int] = {}
        rows = expense_rows(c)
        for r in rows:
            k = (r["date"] or "")[:7]
            if k not in per:
                continue
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            per[k]["total_paise"] += r["amount_paise"]
            per[k]["share1_paise"] += s1
            per[k]["share2_paise"] += s2
            cat = r["category"] or "Uncategorised"
            by_cat[cat] = by_cat.get(cat, 0) + r["amount_paise"]
        hist = category_monthly(rows, keys)   # per-category monthly series + count, aligned to keys
        s = c.execute("SELECT name1, name2 FROM settings WHERE id=1").fetchone()
        return {"months": [per[k] for k in keys], "name1": s["name1"], "name2": s["name2"],
                "by_category": [{"category": k, "amount_paise": v,
                                 "count": hist.get(k, {}).get("count", 0),
                                 "series": hist.get(k, {}).get("series", [0] * len(keys))}
                                for k, v in sorted(by_cat.items(), key=lambda x: -x[1])]}


@router.get("/api/insights")
def insights():
    """Ranked, couple-friendly insight cards — pure math on the existing analytics.
    No LLM, no network: instant, free, and financial data never leaves the server."""
    a = analytics(months=6)   # reuse the month/category series computation
    today = date.today()
    with db() as c:
        raw = balance_payload(c)["raw"]
        srow = c.execute("SELECT MAX(date) AS d FROM settlements").fetchone()
        weeks = None
        if srow and srow["d"]:
            weeks = max(0, (today - date.fromisoformat(srow["d"][:10])).days // 7)
        # descriptions logged in >=3 distinct recent months that aren't recurring rules yet
        existing = {(r["description"] or "").strip().lower()
                    for r in c.execute("SELECT description FROM recurring")}
        rows = c.execute(
            "SELECT description, COUNT(DISTINCT substr(date,1,7)) AS m FROM expenses "
            "WHERE date >= date('now','-6 months') AND TRIM(description) <> '' "
            "GROUP BY LOWER(TRIM(description))"
        ).fetchall()
        candidates = [{"desc": r["description"], "months": r["m"]}
                      for r in rows if r["m"] >= 3
                      and (r["description"] or "").strip().lower() not in existing]
    data = {
        "keys": [m["month"] for m in a["months"]],
        "month_totals": [m["total_paise"] for m in a["months"]],
        "categories": [{"category": x["category"], "series": x["series"]} for x in a["by_category"]],
        "current_day": today.day,
        "days_in_month": monthrange(today.year, today.month)[1],
        "balance_raw": raw,
        "name1": a["name1"], "name2": a["name2"],
        "weeks_since_settle": weeks,
        "recurring_candidates": candidates,
    }
    return {"insights": build_insights(data)}
