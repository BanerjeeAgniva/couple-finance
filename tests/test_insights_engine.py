"""Pure unit checks for insights_engine — no network, no DB. Run: python test_insights_engine.py"""
from insights_engine import (
    build_insights, category_spike, month_forecast, recurring_suggestion,
    settle_nudge, teamwork_win,
)

KEYS = ["2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09"]


def test_settle_nudge():
    # big balance -> nudge, and names/direction follow the sign (raw>0 => name2 owes name1)
    i = settle_nudge(500_000, "Arjun", "Nandini", 1)
    assert i and i["severity"] == "alert" and "Nandini owes Arjun" in i["title"]
    assert settle_nudge(-500_000, "Arjun", "Nandini", 1)["title"].startswith("Arjun owes Nandini")
    # small & fresh -> quiet; small but stale -> still nudges
    assert settle_nudge(50_000, "A", "B", 0) is None
    assert settle_nudge(50_000, "A", "B", 4) is not None
    assert settle_nudge(0, "A", "B", 9) is None


def test_category_spike():
    cats = [{"category": "Swiggy", "series": [1000_00, 1000_00, 1000_00, 1000_00, 2000_00, 500_00]}]
    i = category_spike(cats, KEYS)                    # recent complete month (idx -2) = 2000 vs ~1000 avg
    assert i and i["kind"] == "spike" and i["action"] == "#activity/Swiggy"
    # flat spending -> no spike
    assert category_spike([{"category": "Rent", "series": [x for x in [1000_00] * 6]}], KEYS) is None
    # not enough history
    assert category_spike(cats, KEYS[:2]) is None


def test_month_forecast():
    totals = [10_000_00, 10_000_00, 10_000_00, 10_000_00, 10_000_00, 8_000_00]
    i = month_forecast(totals, KEYS, current_day=10, days_in_month=30)  # 8k/10*30 = 24k >> 10k avg
    assert i and i["kind"] == "forecast"
    # on-pace month -> quiet (₹5k by day 15 of 30 projects to ~₹10k = the average)
    assert month_forecast([10_000_00] * 5 + [5_000_00], KEYS, 15, 30) is None
    # too early in the month -> quiet
    assert month_forecast(totals, KEYS, 2, 30) is None


def test_recurring_suggestion():
    assert recurring_suggestion([{"desc": "Netflix", "months": 4}])["kind"] == "recurring"
    assert recurring_suggestion([{"desc": "Coffee", "months": 2}]) is None
    assert recurring_suggestion([]) is None


def test_teamwork_win():
    # prev complete month (idx -3)=10k, last complete (idx -2)=8k -> 20% drop; idx -1 is partial
    i = teamwork_win([9_000_00, 9_000_00, 9_000_00, 10_000_00, 8_000_00, 3_000_00], KEYS)
    assert i and i["severity"] == "win"
    assert teamwork_win([9_000_00, 9_000_00, 9_000_00, 10_000_00, 10_000_00, 3_000_00], KEYS) is None


def test_build_ranks_alerts_first():
    data = {
        "keys": KEYS,
        "month_totals": [10_000_00, 10_000_00, 10_000_00, 8_000_00, 0, 0],
        "categories": [{"category": "Swiggy", "series": [1000_00, 1000_00, 1000_00, 1000_00, 3000_00, 0]}],
        "current_day": 1, "days_in_month": 30,          # forecast stays quiet (too early)
        "balance_raw": 500_000, "name1": "A", "name2": "B",
        "weeks_since_settle": 5, "recurring_candidates": [{"desc": "Rent", "months": 4}],
    }
    out = build_insights(data)
    assert out and out[0]["severity"] == "alert"         # alerts sort ahead of suggest/win
    assert [i["severity"] for i in out] == sorted((i["severity"] for i in out),
                                                   key={"alert": 0, "suggest": 1, "win": 2}.get)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"ok  {name}")
    print("all insights_engine checks passed")
