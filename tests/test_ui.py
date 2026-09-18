"""End-to-end UI tests — real headless Chromium drives every interactive control.

Boots a real uvicorn server against a throwaway SQLite DB, seeds it over HTTP, then
clicks the actual rendered elements so a regression of ANY inline handler (the class
of bug that shipped when `pickCat` etc. weren't exposed on `window`) fails the build.

Run:  python -m tests.test_ui       (needs: pip install playwright; playwright install chromium)
"""
import base64
import contextlib
import hashlib
import hmac
import json
import os
import pathlib
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
SECRET, PW = "ci-secret", "ci-pass"
# a 1x1 transparent PNG for the avatar-upload flow
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _cookie():
    return hmac.new(SECRET.encode(), b"ok", hashlib.sha256).hexdigest()


def _req(base, method, path, body=None, cookie=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if cookie:
        headers["Cookie"] = f"session={cookie}"
    r = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    return json.load(urllib.request.urlopen(r, timeout=10))


def _wait_up(base, tries=60):
    for _ in range(tries):
        try:
            urllib.request.urlopen(base + "/api/me", timeout=1)
            return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("server did not come up")


@contextlib.contextmanager
def server(seed):
    port = _free_port()
    db = os.path.join(tempfile.mkdtemp(), "ui_test.db")
    env = {**os.environ, "SECRET_KEY": SECRET, "APP_PASSWORD": PW, "DB_PATH": db, "PYTHONUNBUFFERED": "1"}
    env.pop("TURSO_DATABASE_URL", None)
    env.pop("OCR_SPACE_API_KEY", None)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=str(ROOT), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_up(base)
        if seed:
            _seed(base)
        yield base
    finally:
        proc.terminate()
        with contextlib.suppress(Exception):
            proc.wait(timeout=10)
        proc.poll() is None and proc.kill()


def _seed(base):
    ck = _cookie()
    _req(base, "PUT", "/api/settings", {"name1": "Agniva", "name2": "Nandini",
         "income1_paise": 9000000, "income2_paise": 6000000,
         "upi1": "agniva@okhdfcbank", "upi2": "nandini@okaxis"}, ck)
    cats = {c["name"]: c["id"] for c in _req(base, "GET", "/api/categories", None, ck)}
    for d, desc, rs, cat, by in [("2026-09-01", "Sept rent", 30000, "Rent", 1),
                                 ("2026-09-05", "BigBasket haul", 3450, "Groceries", 2),
                                 ("2026-09-09", "Swiggy lunch", 540, "Swiggy", 1)]:
        _req(base, "POST", "/api/expenses", {"date": d, "description": desc,
             "amount_paise": rs * 100, "category_id": cats.get(cat), "paid_by": by}, ck)
    _req(base, "POST", "/api/settlements", {"date": "2026-08-31", "amount_paise": 200000,
         "from_person": 2, "to_person": 1, "note": "August"}, ck)
    nid = _req(base, "POST", "/api/notes", None, ck)["id"]
    _req(base, "PUT", f"/api/notes/{nid}", {"content": "Goa trip\n- [ ] book hotel\n- [x] flights",
         "pinned": True}, ck)


# ---- checks (each raises AssertionError on failure) -------------------------

def _open_add(page):
    page.click('.tab-btn[data-tab="add"]')
    page.wait_for_selector("#tab-add", state="visible")


def check_boot(page):
    page.wait_for_selector("#app", state="visible")
    assert page.locator("#login").is_hidden(), "login overlay should be hidden when authed"


def check_tabs(page):
    for t in ["activity", "settle", "trends", "recurring", "scratch", "settings", "add"]:
        page.click(f'.tab-btn[data-tab="{t}"]')
        page.wait_for_selector(f"#tab-{t}", state="visible")
    page.click("#balance-chip")   # goTab('settle')
    page.wait_for_selector("#tab-settle", state="visible")


def check_category_pick(page):
    """THE regression: clicking a generated .cat-tile must select it (pickCat on window)."""
    _open_add(page)
    page.click("#cat-btn")
    page.wait_for_selector("#cat-pop", state="visible")
    tile = page.locator('#cat-pop .cat-tile', has_text="Swiggy").first
    cid = tile.get_attribute("data-id")
    tile.click()
    page.wait_for_selector("#cat-pop", state="hidden")
    assert page.locator("#cat-select").input_value() == cid, "category not selected"
    assert "Swiggy" in (page.locator("#cat-btn").get_attribute("aria-label") or ""), "cat-btn label not synced"


def check_payer_switch(page):
    _open_add(page)
    page.click('#paidby-seg .seg-opt[data-p="2"]')
    assert page.locator("#paidby-seg").get_attribute("data-sel") == "2"
    page.click('#paidby-seg .seg-opt[data-p="1"]')
    assert page.locator("#paidby-seg").get_attribute("data-sel") == "1"


def check_split_custom(page):
    _open_add(page)
    page.select_option("#split-sel", "custom")     # setSplitAdd
    page.wait_for_selector("#ov-custom", state="visible")
    page.click('#ov-custom .ov-quick[data-a="100"]')   # wireOvQuick
    page.select_option("#split-sel", "ratio")
    page.wait_for_selector("#ov-custom", state="hidden")


def check_add_expense(page):
    _open_add(page)
    page.fill('#expense-form [name="amount"]', "123")
    page.fill('#expense-form [name="description"]', "UI test expense")
    page.click('#expense-form button[type="submit"]')     # addExpense
    page.wait_for_selector("#toasts .toast", state="visible")
    page.wait_for_function("document.querySelector('#expense-form [name=amount]').value === ''")


def check_edit_and_delete(page):
    page.click('.tab-btn[data-tab="activity"]')
    page.wait_for_selector("#activity-list .row-tap", state="visible")
    page.wait_for_load_state("networkidle")                 # loadActivity settled
    # --- edit (openEdit → saveEdit) ---
    page.locator("#activity-list .row-tap").first.click()
    page.wait_for_selector("#edit-modal", state="visible")
    page.fill('#edit-form [name="amount"]', "777")
    page.click('#edit-form button[type="submit"]')          # saveEdit
    page.wait_for_selector("#edit-modal", state="hidden")
    page.wait_for_load_state("networkidle")                 # let the async refetch settle
    # --- delete (openEdit → deleteFromEdit); assert THAT row disappears (race-proof) ---
    page.locator("#activity-list .row-tap").first.click()
    page.wait_for_selector("#edit-modal", state="visible")
    del_id = page.eval_on_selector("#edit-form [name=id]", "el => el.value")
    page.click('#edit-form .btn-danger')                    # deleteFromEdit (confirm auto-accepted)
    page.wait_for_selector("#edit-modal", state="hidden")
    page.wait_for_selector(f'#activity-list [onclick="openEdit({del_id})"]', state="detached")


def check_settle(page):
    page.click('.tab-btn[data-tab="settle"]')
    page.wait_for_selector("#tab-settle", state="visible")
    if page.locator("#copy-upi").is_visible():
        page.click("#copy-upi")                              # copyUpi
    if page.locator("#settle-controls").is_visible():
        page.fill("#settle-amount", "50")
        page.click('#settle-controls .btn-primary')         # settleUp
        page.wait_for_selector("#toasts .toast", state="visible")
    # delete a settlement from history (the seeded one is always present)
    page.wait_for_selector('#settle-history [onclick*="delSettlement"]', state="visible")
    page.locator('#settle-history [onclick*="delSettlement"]').first.click()   # delSettlement


def check_trends(page):
    page.click('.tab-btn[data-tab="trends"]')
    page.wait_for_selector("#trends-box .chart-card", state="visible")
    page.click('#range-seg .seg-opt[data-m="12"]')
    page.wait_for_selector(".hist-pill", state="visible")
    page.locator(".hist-pill").nth(1).click()               # switch spend-history category
    page.wait_for_selector(".spark", state="visible")


def check_recurring(page):
    page.click('.tab-btn[data-tab="recurring"]')
    page.wait_for_selector("#rec-form", state="visible")
    page.fill('#rec-form [name="amount"]', "1199")
    page.fill('#rec-form [name="description"]', "Broadband")
    page.fill('#rec-form [name="day_of_month"]', "5")
    page.click('#rec-form button[type="submit"]')           # addRecurring
    page.wait_for_selector("#rec-list .row", state="visible")
    page.locator('#rec-list [onclick*="delRecurring"]').first.click()   # delRecurring (dialog accepted)


def check_notes(page):
    page.click('.tab-btn[data-tab="scratch"]')
    page.wait_for_selector("#tab-scratch", state="visible")
    page.locator('#tab-scratch .chip-btn', has_text="New note").click()   # newNote
    page.wait_for_selector("#notes-editor-view", state="visible")
    page.fill("#scratch", "Groceries plan\n- [ ] milk")
    page.click('[onclick="insertChecklistItem()"]')          # insertChecklistItem
    page.wait_for_selector("#checklist-panel", state="visible")
    page.locator('#checklist-panel input[type="checkbox"]').first.check()   # toggleChecklist
    page.click("#pin-btn")                                   # togglePin
    page.click(".back-btn")                                  # backToNotes
    page.wait_for_selector("#notes-list .note-card", state="visible")
    page.locator("#notes-list .note-card").first.click()     # openNote
    page.wait_for_selector("#notes-editor-view", state="visible")
    page.click('[onclick="deleteCurrentNote()"]')            # deleteCurrentNote (dialog accepted)
    page.wait_for_selector("#notes-list-view", state="visible")


def check_settings(page):
    page.click('.tab-btn[data-tab="settings"]')
    page.wait_for_selector("#settings-form", state="visible")
    page.fill('#settings-form [name="income1"]', "95000")
    page.click('#settings-form button[type="submit"]')      # saveSettings
    page.wait_for_selector("#toasts .toast", state="visible")
    # add + remove a category
    page.fill('.add-inline [name="name"]', "Petrol")
    page.click('.add-inline button[type="submit"]')          # addCategory
    page.wait_for_selector('#cat-manage', state="visible")
    page.locator('#cat-manage [onclick*="delCategory"]').first.click()   # delCategory (dialog accepted)
    # theme
    page.click('#theme-seg .seg-opt[data-t="dark"]')         # setTheme
    page.wait_for_function("document.documentElement.dataset.theme === 'dark'")
    page.click('#theme-seg .seg-opt[data-t="light"]')
    page.wait_for_function("document.documentElement.dataset.theme === 'light'")
    # avatar upload (onAvatarPick) + remove
    png = os.path.join(tempfile.mkdtemp(), "a.png")
    pathlib.Path(png).write_bytes(PNG_1PX)
    page.set_input_files("#av-in-1", png)                    # onAvatarPick(1) → PUT /api/avatar
    page.wait_for_selector("#av-rm-1", state="visible")      # Remove link appears once a photo is set
    page.click("#av-rm-1")                                   # removeAvatar(1)
    # export CSV (exportCsv → download)
    with page.expect_download() as dl:
        page.click('[onclick="exportCsv()"]')
    assert dl.value.suggested_filename.endswith(".csv"), "export did not download a CSV"


def check_category_budget(page):
    """Set a monthly cap on a category in Settings; the Add-tab picker then shows the nudge."""
    page.click('.tab-btn[data-tab="settings"]')
    page.wait_for_selector("#settings-form", state="visible")
    page.fill('.add-inline [name="name"]', "Budgeted")
    page.click('.add-inline button[type="submit"]')          # addCategory
    chip = page.locator('#cat-manage .cat-tag', has_text="Budgeted")
    chip.wait_for(state="visible")
    inp = chip.locator(".cat-budget")
    inp.fill("2000")
    inp.dispatch_event("change")                             # setBudget → PUT /api/categories/{id}
    page.wait_for_selector("#toasts .toast", state="visible")
    # cap round-trips through the settings re-render
    assert page.locator('#cat-manage .cat-tag', has_text="Budgeted").locator(".cat-budget").input_value() == "2000"
    # Add tab: picking the budgeted category surfaces the quiet hint
    _open_add(page)
    page.click("#cat-btn")
    page.wait_for_selector("#cat-pop", state="visible")
    page.locator('#cat-pop .cat-tile', has_text="Budgeted").first.click()
    page.wait_for_selector("#cat-budget-hint", state="visible")
    assert "of ₹2,000" in (page.locator("#cat-budget-hint").text_content() or ""), "budget hint missing/wrong"

    def add_budgeted(amount):
        _open_add(page)
        page.click("#cat-btn")
        page.wait_for_selector("#cat-pop", state="visible")
        page.locator('#cat-pop .cat-tile', has_text="Budgeted").first.click()
        page.fill('#expense-form [name="amount"]', amount)
        page.fill('#expense-form [name="description"]', "budget test")
        page.click('#expense-form button[type="submit"]')
        page.wait_for_function("document.querySelector('#expense-form [name=amount]').value === ''")

    # near-limit branch: spend 80% of the ₹2,000 cap → hint turns amber
    add_budgeted("1600")
    page.wait_for_function("document.querySelector('#cat-budget-hint')?.classList.contains('near')")
    # over-budget branch: push past the cap → "Over budget by ₹X"
    add_budgeted("500")   # total ₹2,100
    page.wait_for_function("document.querySelector('#cat-budget-hint')?.classList.contains('over')")
    assert "Over budget by ₹100" in (page.locator("#cat-budget-hint").text_content() or ""), "over-budget text wrong"


SEEDED_CHECKS = [
    check_boot, check_tabs, check_category_pick, check_payer_switch, check_split_custom,
    check_add_expense, check_edit_and_delete, check_settle, check_trends, check_recurring,
    check_notes, check_settings, check_category_budget,
]


def check_login_and_onboarding(base, browser):
    # 1) unauthenticated context → login form; wrong password → error; right password → app
    ctx = browser.new_context()
    page = ctx.new_page()
    page.goto(base + "/")
    page.wait_for_selector("#login", state="visible")
    page.fill("#pw", "wrong-password")
    page.click('#login button[type="submit"]')              # doLogin (wrong)
    page.wait_for_function("document.querySelector('#login-err').textContent.length > 0 "
                           "|| document.querySelector('#toasts .toast')")
    page.fill("#pw", PW)
    page.click('#login button[type="submit"]')              # doLogin (right)
    # fresh DB → onboarding overlay appears (Person 1/2 defaults)
    page.wait_for_selector("#onboarding", state="visible")
    ctx.close()

    # 2) onboarding: fill incomes → ratio strip lights up → saveOnboarding
    ctx = browser.new_context()
    ctx.add_cookies([{"name": "session", "value": _cookie(), "url": base}])
    page = ctx.new_page()
    page.goto(base + "/")
    page.wait_for_selector("#onboarding", state="visible")
    page.fill('#onb-form [name="name1"]', "Agniva")
    page.fill('#onb-form [name="name2"]', "Nandini")
    page.fill('#onb-form [name="income1"]', "90000")
    page.fill('#onb-form [name="income2"]', "60000")
    page.wait_for_selector("#onb-split", state="visible")   # live ratio strip
    page.click('#onb-form button[type="submit"]')           # saveOnboarding
    page.wait_for_selector("#app", state="visible")
    page.wait_for_selector("#onboarding", state="hidden")
    ctx.close()


def run():
    results = []

    def record(name, fn):
        try:
            fn()
            results.append((name, None))
            print(f"ok   {name}")
        except Exception as e:  # noqa: BLE001 - report every failure, keep going
            results.append((name, repr(e)))
            print(f"FAIL {name}: {e!r}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        # seeded flows
        with server(seed=True) as base:
            ctx = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
            ctx.add_cookies([{"name": "session", "value": _cookie(), "url": base}])
            page = ctx.new_page()
            page.on("dialog", lambda d: d.accept())         # auto-accept confirm() on deletes
            page.goto(base + "/")
            for fn in SEEDED_CHECKS:
                record(fn.__name__, lambda fn=fn: fn(page))
            ctx.close()
        # login + onboarding (fresh DB)
        with server(seed=False) as base:
            record("check_login_and_onboarding",
                   lambda: check_login_and_onboarding(base, browser))
        browser.close()

    failed = [n for n, err in results if err]
    print(f"\n{len(results) - len(failed)}/{len(results)} UI checks passed")
    if failed:
        raise SystemExit("FAILED UI checks: " + ", ".join(failed))
    print("all UI checks passed")


if __name__ == "__main__":
    run()
