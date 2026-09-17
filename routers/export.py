"""CSV export of expenses (and optionally settlements)."""
import csv
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from auth import require_auth
from db import db, expense_rows, global_ratio, post_due_recurring
from money import resolve_ratio, split

router = APIRouter(dependencies=[Depends(require_auth)])


@router.get("/api/export")
def export(days: int = 30, settlements: int = 0):
    with db() as c:
        post_due_recurring(c)
        g1, g2 = global_ratio(c)
        s = c.execute("SELECT name1, name2 FROM settings WHERE id=1").fetchone()
        buf = io.StringIO()
        w = csv.writer(buf)
        head = ["date", "description", "category", "amount_rs", "paid_by",
                "paid_to", f"{s['name1']}_share_rs", f"{s['name2']}_share_rs"]
        if settlements:
            head = ["type"] + head
        w.writerow(head)
        rowdays = None if days <= 0 else days      # days<=0 => all time
        def row(vals):
            w.writerow((["expense"] + vals) if settlements else vals)
        for r in expense_rows(c, days=rowdays):
            r1, r2 = resolve_ratio(r["override_r1"], r["override_r2"], g1, g2)
            s1, s2 = split(r["amount_paise"], r1, r2)
            payer = s["name1"] if r["paid_by"] == 1 else s["name2"]
            row([r["date"], r["description"], r["category"] or "",
                 f"{r['amount_paise']/100:.2f}", payer, r["paid_to"] or "",
                 f"{s1/100:.2f}", f"{s2/100:.2f}"])
        if settlements:
            q = "SELECT * FROM settlements"
            args = []
            if rowdays:
                q += " WHERE date >= date('now', ?)"; args.append(f"-{rowdays} days")
            q += " ORDER BY date"
            for r in c.execute(q, args):
                frm = s["name1"] if r["from_person"] == 1 else s["name2"]
                to = s["name1"] if r["to_person"] == 1 else s["name2"]
                w.writerow(["settlement", r["date"], f"{frm} paid {to}", "", f"{r['amount_paise']/100:.2f}",
                            frm, to, "", ""])
        buf.seek(0)
        fname = f"couple_finance_{'all' if days <= 0 else 'last_' + str(days) + '_days'}.csv"
        return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                                 headers={"Content-Disposition": f'attachment; filename="{fname}"'})
