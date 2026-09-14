# Couple Finance — Design system ("The Shared Ledger")

Crisp modern-fintech for a **two-person household**. The signature that keeps it
off the generic-banking-app path: both partners are *co-present everywhere*, each
a fixed colour, and the balance is a **directional statement between two named
people** (money flowing A→B) — never a lone hero metric. Mode: **Operate**.

## Colour (tokens in `static/style.css :root`)
- Ground `--ground` cool paper-white `#f4f5f7`; surfaces `--card` white; ink `--ink` `#0b0f17`.
- **Person A** `--a` teal `#0f766e`; **Person B** `--b` burnt-orange `#c2410c`. These two
  colours carry identity throughout: avatars, shares, the split bar, the flow arrow's gradient.
- Actions are ink-black (light) / teal (dark). Strategy: **Restrained** — neutrals + the two person hues.
- Dark theme (night phone use) via `prefers-color-scheme`: ground `#0b0f17`, brighter teal/orange.

## Type
- **Archivo** (Google Fonts) everywhere — a precise grotesk; weights 400–800.
- Money uses `font-variant-numeric: tabular-nums` (`.flow-amt`, `.row-amt`, `.big`, `.balance-chip`, …)
  for column-aligned figures — the account-book texture without a monospace costume.
- Headings `letter-spacing:-0.03em`; body 15px.

## Layout
- **Shell:** left rail (desktop ≥720px) / fixed bottom tab bar (phone), mirrored from `#tabs`.
  `[hidden]{display:none!important}` reset is required (our `display:grid` rules override the attribute).
- Content column `max-width:720px`. Cards = `.hero` / `.sheet`: hairline `--line` border + soft
  offset/blur shadow (`--shadow-sm/md`), radius 14–20px.
- Mobile: `min-width:0` on form controls, `minmax(0,1fr)` grids, and the compact balance flow
  stacks — no horizontal scroll at 390px.

## Signature components
- **Balance flow** (`flowHTML` in `app.js`): debtor chip → gradient arrow → creditor chip, amount,
  "X owes Y". `flow-lg` is the Settle hero; compact version tops the Add tab; a chip mirrors it in the topbar.
- **Income split strip:** proportional teal/orange bar + %.
- **Ledger rows** (`.row`): payer avatar, description, `date · category · → merchant`, amount, per-person shares.
- **Segmented "paid by":** two person-coloured options.
- Icons: authored inline SVG sprite (`#i-*`), single 1.5–1.8px stroke. No emoji as icons.

## Motion
- Section enter: one `rise` ease-out; `prefers-reduced-motion` disables all. Avoid animating layout props.

## v2 components (settle-up extension)
- **Activity feed** (`loadActivity`): expenses + settlement rows merged; settlement row uses a check avatar, teal amount, muted "X paid Y". Expense rows are tap-to-edit (`.row-tap` + `.row-edit` pencil).
- **Settle**: `.btn-upi` (teal) opens a `upi://pay` link; **QR fallback** (`.qr-box`, self-hosted `qrcode.min.js`, dark-on-white so it scans in any theme) + **tap-to-copy UPI ID** (`.copy-upi`) for iPhone/desktop/cross-device; partial-amount field + "Mark settled" in `.settle-controls`; settlement history with undo. After tapping Pay-via-UPI, a `visibilitychange`-gated **"Did you pay?" prompt** (`#pay-prompt`) records the settlement on return.
- **Edit modal** (`.modal`/`.modal-card`): bottom-sheet on phone, centered on desktop; reuses the sheet form; Delete + Save.
- **Quick-split segmented** (`#split-seg`): By income / 50:50 / Custom; custom row has `.ov-quick` chips for 100% either person.
- **Trends** charts: `.bar-chart` stacked monthly bars (A teal bottom / B orange top) + category `.cat-line` bars; `#range-seg` 3m/6m/12m.
- **Receipt scan** (`.chip-btn` + `.scan-status`): hidden unless `/api/me` reports `ocr:true`.
- Settings gain per-person UPI IDs (`.upi-in`).

## Onboarding & empty states
- **First-run overlay** (`.onb`, `#onb-form`): shown only while settings are the seed defaults
  (`name1==="Person 1" && name2==="Person 2"`) — server-driven so the second partner never re-sees it;
  a local `cf_onb_skip` suppresses it after "I'll set this up later". Captures names + incomes with a
  live split-ratio preview (the aha) + optional UPI. Reuses the login-card aesthetic.
- **Empty states** via `emptyState(icon,title,body,cta)`: `.empty-title` + `.empty-body` + a `.btn-sm`
  CTA that routes to Add. Used on Activity, Trends (category area), Recurring.

## Notes for future work
- New tabs: add a `.tab-btn` to `#tabs` (bottom bar auto-mirrors) + a `TAB_TITLE` entry + a `#tab-<name>` section.
- Keep money as integer paise end-to-end; render with `rs()`/`rs0()`.
- Detector: `node <impeccable>/scripts/detect.mjs --json static/*.{html,css,js}` — currently clean.
