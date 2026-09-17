"""Runnable checks for the money path. `python test_money.py`."""
import os
os.environ["DB_PATH"] = "/tmp/couple_test.db"  # keep import-time init_db off the real db
from app import split, resolve_ratio, compute_balance, upi_link, parse_receipt_total, category_monthly


def test_split_sums_exactly():
    for amt in (1, 3, 100, 10001, 99999, 123457):
        for r1, r2 in ((1, 1), (60, 40), (7, 3), (1, 2)):
            s1, s2 = split(amt, r1, r2)
            assert s1 + s2 == amt, (amt, r1, r2, s1, s2)
            assert s1 >= 0 and s2 >= 0


def test_split_ratio():
    assert split(10000, 60, 40) == (6000, 4000)
    assert split(10000, 1, 1) == (5000, 5000)
    # odd paisa lands on share1 via subtraction
    assert split(3, 1, 1) == (2, 1)


def test_resolve_override_wins():
    assert resolve_ratio(7, 3, 1, 1) == (7, 3)      # override present
    assert resolve_ratio(None, None, 6, 4) == (6, 4)  # falls back to global
    assert resolve_ratio(7, None, 6, 4) == (6, 4)     # partial override ignored


def test_balance_person2_owes_person1():
    # person1 paid 10000, split 60:40 -> person2 owes 4000
    bal = compute_balance([(10000, 1, None, None)], [], 60, 40)
    assert bal == 4000


def test_balance_flips_with_payer():
    # person2 paid 10000, split 60:40 -> person1 owes their 6000 share
    bal = compute_balance([(10000, 2, None, None)], [], 60, 40)
    assert bal == -6000


def test_settlement_reduces_debt():
    exp = [(10000, 1, None, None)]  # person2 owes person1 4000
    setl = [(4000, 2, 1)]           # person2 pays person1 4000
    assert compute_balance(exp, setl, 60, 40) == 0


def test_override_used_in_balance():
    # global 1:1 would give 5000, but override 90:10 -> person2 owes 1000
    bal = compute_balance([(10000, 1, 90, 10)], [], 1, 1)
    assert bal == 1000


def test_upi_link():
    link = upi_link("priya@okhdfc", "Priya", 553160)
    assert link.startswith("upi://pay?")
    assert "pa=priya%40okhdfc" in link
    assert "am=5531.60" in link and "cu=INR" in link


def test_parse_receipt_total():
    assert parse_receipt_total("BIG BAZAAR\nItem 100.00\nSub Total 400.00\nGrand Total 428.00") == 42800
    assert parse_receipt_total("shop\n12.50\n999.99\nno label") == 99999   # largest fallback
    assert parse_receipt_total("nothing numeric") is None


def test_category_monthly():
    keys = ["2026-07", "2026-08", "2026-09"]
    rows = [
        {"date": "2026-08-02", "category": "Swiggy", "amount_paise": 500},
        {"date": "2026-08-20", "category": "Swiggy", "amount_paise": 300},
        {"date": "2026-09-01", "category": "Swiggy", "amount_paise": 200},
        {"date": "2026-09-05", "category": "Amazon", "amount_paise": 1000},
        {"date": "2026-06-30", "category": "Swiggy", "amount_paise": 999},  # out of range -> ignored
        {"date": "2026-09-09", "category": None, "amount_paise": 40},        # None -> "Uncategorised"
    ]
    out = category_monthly(rows, keys)
    assert out["Swiggy"]["count"] == 3
    assert out["Swiggy"]["series"] == [0, 800, 200]      # aligned to keys, Aug summed, July 0
    assert out["Amazon"]["series"] == [0, 0, 1000]
    assert out["Uncategorised"]["count"] == 1 and out["Uncategorised"]["series"] == [0, 0, 40]
    assert "Swiggy" in out and sum(out["Swiggy"]["series"]) == 1000  # the June row was excluded
    assert category_monthly([], keys) == {}                # empty input


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"ok  {name}")
    print("all passed")
