"""Pure insight generation — no FastAPI, no DB, no environment.

Turns the numbers the app already computes (per-month totals, per-category monthly
series, the settle-up balance) into a ranked list of couple-friendly insight cards.
Every function here is a pure function of its inputs, so it's trivially testable
(see test_insights_engine.py) and adds zero latency and zero cost — no LLM, no
network, financial data never leaves the server.

An insight is a dict: {kind, severity, title, detail, action?}
  severity: "alert" (act soon) | "suggest" (a helpful nudge) | "win" (positive)
  action:   optional hash route for the UI to deep-link (e.g. "#settle").
"""
from urllib.parse import quote

# Thresholds are deliberately conservative so cards stay rare and meaningful.
SETTLE_MIN_PAISE = 200_000       # ₹2,000 unsettled before we nudge
SETTLE_STALE_WEEKS = 3           # ...or any balance left this long
SPIKE_RATIO = 1.4                # a category 40%+ over its own average
SPIKE_MIN_DELTA_PAISE = 50_000   # ...and at least ₹500 more, so tiny bumps stay quiet
FORECAST_RATIO = 1.2             # projected month 20%+ over recent average
WIN_DROP_RATIO = 0.9             # month came in 10%+ under the previous one
RECURRING_MIN_MONTHS = 3         # same description this many months running

_SEVERITY_ORDER = {"alert": 0, "suggest": 1, "win": 2}


def _rs(paise: int) -> str:
    return f"₹{round(paise / 100):,}"


def _pct(x: float) -> int:
    return round(x * 100)


def settle_nudge(balance_raw, name1, name2, weeks_since_settle):
    """Fronting money is the #1 couple money-friction point — nudge to settle."""
    amt = abs(balance_raw)
    stale = weeks_since_settle is not None and weeks_since_settle >= SETTLE_STALE_WEEKS
    if amt < SETTLE_MIN_PAISE and not (stale and amt > 0):
        return None
    debtor, creditor = (name2, name1) if balance_raw > 0 else (name1, name2)
    weeks = f" It's been {weeks_since_settle} weeks since you last settled." if stale else ""
    return {
        "kind": "settle", "severity": "alert",
        "title": f"{debtor} owes {creditor} {_rs(amt)}",
        "detail": f"One tap over UPI squares you up.{weeks}",
        "action": "#settle",
    }


def category_spike(categories, keys):
    """Most recent *complete* month of a category vs its own trailing average."""
    if len(keys) < 3:
        return None
    best = None
    for c in categories:
        s = c["series"]
        recent, prior = s[-2], s[:-2]              # -1 is the current (partial) month
        prior_nonzero = [v for v in prior if v > 0]
        if recent <= 0 or len(prior_nonzero) < 1:
            continue
        avg = sum(prior_nonzero) / len(prior_nonzero)
        if recent >= SPIKE_RATIO * avg and recent - avg >= SPIKE_MIN_DELTA_PAISE:
            over = recent - avg
            if best is None or over > best[0]:
                best = (over, c["category"], recent, avg)
    if best is None:
        return None
    _, cat, recent, avg = best
    return {
        "kind": "spike", "severity": "alert",
        "title": f"{cat} is up {_pct(recent / avg - 1)}%",
        "detail": f"Last month you spent {_rs(recent)} on {cat} — usually about {_rs(round(avg))}.",
        "action": "#activity/" + quote(cat, safe=""),   # matches the encoded filter route from the feed
    }


def month_forecast(month_totals, keys, current_day, days_in_month):
    """Pace-project the current (partial) month vs the recent average."""
    if len(keys) < 3 or current_day < 5 or days_in_month <= 0:
        return None                                # too early to project meaningfully
    so_far = month_totals[-1]
    if so_far <= 0:
        return None
    projected = round(so_far / current_day * days_in_month)
    prior = [v for v in month_totals[:-1] if v > 0]
    if not prior:
        return None
    avg = sum(prior) / len(prior)
    if projected < FORECAST_RATIO * avg:
        return None
    return {
        "kind": "forecast", "severity": "suggest",
        "title": f"On pace for {_rs(projected)} this month",
        "detail": f"That's about {_rs(round(projected - avg))} over your recent monthly average of {_rs(round(avg))}.",
    }


def recurring_suggestion(candidates):
    """A description logged several months running probably wants to be a recurring rule."""
    if not candidates:
        return None
    top = max(candidates, key=lambda c: c["months"])
    if top["months"] < RECURRING_MIN_MONTHS:
        return None
    return {
        "kind": "recurring", "severity": "suggest",
        "title": f"Make “{top['desc']}” recurring?",
        "detail": f"You've logged it {top['months']} months running — auto-post it each month instead.",
        "action": "#recurring",
    }


def teamwork_win(month_totals, keys):
    """Celebrate a real month-over-month drop (last *complete* month vs the one before)."""
    if len(keys) < 3:
        return None
    prev, last = month_totals[-3], month_totals[-2]   # -1 is the current partial month
    if prev <= 0 or last <= 0 or last >= WIN_DROP_RATIO * prev:
        return None
    return {
        "kind": "win", "severity": "win",
        "title": f"You spent {_rs(prev - last)} less last month \U0001f389",
        "detail": f"{_rs(last)} vs {_rs(prev)} the month before — nice teamwork.",
    }


def build_insights(data: dict) -> list[dict]:
    """Run every generator over the gathered data and return a ranked, non-null list.

    data keys: month_totals, keys, categories, current_day, days_in_month,
               balance_raw, name1, name2, weeks_since_settle, recurring_candidates.
    """
    keys = data["keys"]
    generated = [
        settle_nudge(data["balance_raw"], data["name1"], data["name2"], data.get("weeks_since_settle")),
        category_spike(data["categories"], keys),
        month_forecast(data["month_totals"], keys, data["current_day"], data["days_in_month"]),
        recurring_suggestion(data.get("recurring_candidates") or []),
        teamwork_win(data["month_totals"], keys),
    ]
    insights = [g for g in generated if g]
    insights.sort(key=lambda i: _SEVERITY_ORDER.get(i["severity"], 9))
    return insights
