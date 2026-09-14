# Couple Finance — Future scope

Ideas captured but not yet built. Ordered roughly by value/effort. Nothing here is committed.

## Tab enhancements (in existing tabs — the "main" bundle, deferred)

### Activity — search + filter + date grouping
- Text search over description / paid-to.
- Filter chips: by person (paid by), by category, this-month / range.
- Date-group headers ("Today", "Yesterday", "12 Sep") instead of a flat list.
- Optional per-day or per-month subtotal.

### Trends — deeper insights
- Month-vs-last-month change ("↑ 12% vs Aug").
- Top merchant, monthly average, biggest single expense.
- Each person's % of total spend over the range.
- (Budgets per category belong to the couple-money layer below.)

### Add — faster entry
- Live split preview: show "Agniva ₹X · Nandini ₹Y" as the amount is typed, before saving.
- Amount quick-chips (+₹50 / ₹100 / ₹500).
- "Duplicate last expense".

### Recurring — management
- Edit an existing recurring item (today: add/delete only).
- Pause / resume a recurring item.
- Show next post date ("next: 1 Oct") and a "₹X/month committed" total.

## Couple-money layer (bigger, still deferred)
- Category **budgets** with progress bars and gentle over-budget cues.
- Shared **savings goals** ("₹50k Goa trip") with contributions.
- Auto **monthly statement** ("September: ₹50,689 spent, here's the split, you're square / owe ₹X").
- Security-deposit / reserve tracking (split now, adjust later).

## Premium-style (heavier)
- Bank/card **CSV import** → auto-create & categorise expenses.
- (Receipt OCR already shipped.)

## Groups feature (major — architectural)
Today the app is deliberately **two-person**: one shared ledger, one income ratio, person 1 / person 2
everywhere, a single shared password. "Groups" (multiple people and/or multiple
separate ledgers) is a large change, not an in-tab tweak. What it would require:

- **Data model:** a `groups` table; `members` (N people per group, not just 2); every
  `expenses` / `settlements` / `recurring` / `notes` row scoped by `group_id`. Splits generalise from
  a 2-way ratio to per-member shares (equal / exact / %/ shares), and balances become an
  N×N net that needs a **debt-simplification** algorithm (currently trivial for 2 people).
- **Identity/auth:** the single shared password no longer fits — needs per-user accounts (login),
  so the app knows *who* is acting and which groups they belong to. This is the biggest lift.
- **UI:** a group switcher (could live in the top bar / Settings, no new tab), per-group balance,
  "who owes whom" across many people, invite/join a group.
- **Migration:** wrap the existing couple ledger as the first group with two members.

**Assessment:** high effort and it changes the product's identity (couple tool → general splitter).
Recommended only if the goal shifts from "just us two" to "us + flatmates/friends/trips". If the
need is just occasional non-couple splits (e.g. a trip with friends), a lighter option is a
**second named ledger** (a "trip" ledger) reusing the two-person model, without full multi-user groups.

## Performance (mostly done)
- ✅ **Keep-alive** GitHub Action (repo public) pings `/api/me` every 10 min → no Render cold start.
- ✅ `/api/bootstrap` (one round trip on load) + self-hosted Archivo fonts.
- **Region co-location (optional, needs user):** you're in India but Render may be US + Turso is
  Tokyo. Fastest = recreate the Render service in **Singapore** + move Turso to **Mumbai
  `aws-ap-south-1`** (Turso side is free via CLI; Render region needs a dashboard recreate → new
  build, same URL if same name).
- **Leave Render entirely (big):** rewrite backend to **Cloudflare Workers + D1** (SQLite at edge,
  ~0 cold start, generous free tier) — removes cold start natively and cuts latency, but it's a full
  Python→JS rewrite (auth, OCR proxy, migrations, all endpoints). Only if you outgrow Render free.

## Smaller polish / infra
- Silence the Render health-check `HEAD /` 405 (add a HEAD route).
- Per-row date / split column in bulk entry (currently shared date + income split).
- Recurring "post now" button; notes reminders.
