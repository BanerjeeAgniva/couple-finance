"""Pure money / domain logic — no FastAPI, no DB, no environment.

Everything here is a pure function of its inputs, so it's trivially testable
(see test_money.py) and reusable. Money is integer paise throughout.
"""
import re
import urllib.parse


def split(amount_paise: int, r1: int, r2: int) -> tuple[int, int]:
    """Split amount by ratio r1:r2. share1 gets any leftover paisa so the two
    shares always sum back to exactly amount_paise."""
    if r1 + r2 <= 0:
        raise ValueError("ratio must be positive")
    share1 = round(amount_paise * r1 / (r1 + r2))
    # ponytail: derive share2 by subtraction so shares always sum to the total
    share2 = amount_paise - share1
    return share1, share2


def resolve_ratio(row_r1, row_r2, global_r1, global_r2) -> tuple[int, int]:
    """Per-expense override wins over the global ratio when present."""
    if row_r1 is not None and row_r2 is not None:
        return row_r1, row_r2
    return global_r1, global_r2


def compute_balance(expenses, settlements, global_r1, global_r2) -> int:
    """Net paise person 2 owes person 1 (negative = person 1 owes person 2).

    expenses: iterable of (amount_paise, paid_by, override_r1, override_r2)
    settlements: iterable of (amount_paise, from_person, to_person)
    """
    bal = 0  # positive => person 2 owes person 1
    for amount, paid_by, or1, or2 in expenses:
        r1, r2 = resolve_ratio(or1, or2, global_r1, global_r2)
        share1, share2 = split(amount, r1, r2)
        if paid_by == 1:
            bal += amount - share1   # person 2 owes their share to person 1
        else:
            bal -= amount - share2   # person 1 owes their share to person 2
    for amount, frm, to in settlements:
        # a payment from 2 to 1 reduces what 2 owes 1
        bal += amount if frm == 1 else -amount
    return bal


def upi_link(vpa: str, name: str, amount_paise: int, note: str = "Couple Finance") -> str:
    """Build a UPI intent URL that opens GPay/PhonePe/etc. with the payee prefilled."""
    q = urllib.parse.urlencode({
        "pa": vpa, "pn": name, "am": f"{amount_paise / 100:.2f}", "cu": "INR", "tn": note,
    })
    return "upi://pay?" + q


def parse_receipt_total(text: str) -> int | None:
    """Best-effort grand total in paise from OCR'd receipt text.
    Prefer an amount on a line mentioning total/amount/grand; else the largest amount seen."""
    amt_re = re.compile(r"(?:₹|rs\.?|inr)?\s*([0-9][0-9,]*\.[0-9]{2}|[0-9][0-9,]{2,})", re.I)
    def to_paise(s):
        return round(float(s.replace(",", "")) * 100)
    labelled = []
    for line in text.splitlines():
        if re.search(r"\b(grand\s*total|total|amount|balance|net\s*payable)\b", line, re.I) \
           and not re.search(r"sub\s*total", line, re.I):
            labelled += [to_paise(m) for m in amt_re.findall(line)]
    if labelled:
        return max(labelled)
    allamts = [to_paise(m) for m in amt_re.findall(text)]
    return max(allamts) if allamts else None


def category_monthly(rows, keys):
    """Per-category monthly spend + transaction count over the given month keys.

    rows: iterable of mappings with 'date' (ISO string), 'category', 'amount_paise'.
    keys: ['YYYY-MM', ...] oldest->newest.
    Returns {category: {'count': int, 'series': [paise per key]}}, series aligned to keys, 0-filled.
    """
    idx = {k: i for i, k in enumerate(keys)}
    out: dict[str, dict] = {}
    for r in rows:
        i = idx.get((r["date"] or "")[:7])
        if i is None:
            continue
        cat = r["category"] or "Uncategorised"
        e = out.get(cat) or out.setdefault(cat, {"count": 0, "series": [0] * len(keys)})
        e["count"] += 1
        e["series"][i] += r["amount_paise"]
    return out
