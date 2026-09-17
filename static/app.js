// --- helpers ---------------------------------------------------------------
const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);
const api = async (url, opts) => {
  const r = await fetch(url, { credentials: "same-origin", ...opts });
  if (r.status === 401) { showLogin(); throw new Error("unauth"); }
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || r.statusText);
  return r.headers.get("content-type")?.includes("json") ? r.json() : r;
};
const rs = (p) => "₹" + (p / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const rs0 = (p) => "₹" + Math.round(p / 100).toLocaleString("en-IN");
const toPaise = (r) => Math.round(parseFloat(r) * 100);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const mLabel = (k) => new Date(k + "-01T00:00").toLocaleDateString("en-IN", { month: "short" });
const jbody = (o) => ({ method: o.method || "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(o.body) });
const fmtDate = (iso) => { const d = new Date(iso + "T00:00"); return isNaN(d) ? iso : d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }); };
const ls = { get: (k) => { try { return localStorage.getItem(k); } catch { return null; } },
             set: (k, v) => { try { localStorage.setItem(k, v); } catch {} },
             del: (k) => { try { localStorage.removeItem(k); } catch {} } };

// --- toasts ----------------------------------------------------------------
function toast(msg, type = "ok") {
  const t = document.createElement("div");
  t.className = "toast " + type;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  requestAnimationFrame(() => t.classList.add("in"));
  setTimeout(() => { t.classList.remove("in"); setTimeout(() => t.remove(), 250); }, 2500);
}
window.addEventListener("unhandledrejection", (e) => {
  const m = e.reason && e.reason.message;
  if (m && m !== "unauth") toast(m, "err");   // unauth already routes to login
});

// --- theme (light / dark / system) -----------------------------------------
const _mql = matchMedia("(prefers-color-scheme: dark)");
function resolveTheme() {
  const p = ls.get("cf_theme");
  return (p === "light" || p === "dark") ? p : (_mql.matches ? "dark" : "light");
}
function applyTheme() {
  const t = resolveTheme();
  document.documentElement.dataset.theme = t;
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.content = t === "dark" ? "#0b0f17" : "#f4f5f7";
  const seg = $("#theme-seg");
  if (seg) seg.querySelectorAll(".seg-opt").forEach((b) => b.classList.toggle("on", b.dataset.t === (ls.get("cf_theme") || "system")));
}
function setTheme(t) {
  if (t === "system") ls.del("cf_theme"); else ls.set("cf_theme", t);
  applyTheme();
}
_mql.addEventListener("change", () => { if (!ls.get("cf_theme")) applyTheme(); });

let SETTINGS = null, CONFIG = { ocr: false }, ACT_BY_ID = {};
let CURRENT_TAB = "add", SETTINGS_DIRTY = false;
const initial = (name, fb) => { const t = (name || "").trim(); return t ? t[0].toUpperCase() : fb; };
const person = (p) => p === 1
  ? { n: SETTINGS.name1, cls: "chip-a", letter: initial(SETTINGS.name1, "A"), color: "var(--a)", photo: SETTINGS.avatar1 || null }
  : { n: SETTINGS.name2, cls: "chip-b", letter: initial(SETTINGS.name2, "B"), color: "var(--b)", photo: SETTINGS.avatar2 || null };
// avatar chip: photo if set, else the person's coloured initial. `extra` = inline style additions.
function avatarChip(p, cls = "chip", extra = "") {
  const pr = person(p);
  if (pr.photo) return `<span class="${cls} ${pr.cls} has-photo" style="background-image:url('${pr.photo}');${extra}"></span>`;
  return `<span class="${cls} ${pr.cls}" style="${extra}">${pr.letter}</span>`;
}

// category name -> drawn icon (keyword match, own/open-source-style SVGs in the sprite)
const CAT_ICONS = [
  // delivery apps first, so the brand name wins over the generic grocery/dining/shopping match
  [["swiggy", "zomato", "food delivery", "eatsure"], "i-cat-delivery"],
  [["blinkit", "zepto", "instamart", "pronto", "dunzo", "quick"], "i-cat-quick"],
  [["amazon", "flipkart", "myntra", "meesho", "parcel", "courier", "delivery"], "i-cat-package"],
  [["snabbit", "urbanclap", "urban company", "service", "salon", "repair", "plumber", "electrician", "handyman"], "i-cat-services"],
  [["furlenco", "rentomojo", "rentmojo"], "i-cat-furniture"],  // before "rent", since these contain it
  [["rent", "mortgage", "lease"], "i-cat-rent"],
  [["grocer", "supermarket", "mart", "bigbasket", "zepto", "blinkit"], "i-cat-groceries"],
  [["eat", "dining", "restaurant", "food", "swiggy", "zomato", "cafe", "dinner", "lunch"], "i-cat-dining"],
  [["util", "electric", "power", "water", "gas", "internet", "wifi", "phone", "broadband", "bill", "trash", "clean"], "i-cat-utilities"],
  [["travel", "flight", "plane", "hotel", "trip", "airbnb", "vacation"], "i-cat-travel"],
  [["transport", "uber", "rapido", "ola", "taxi", "cab", "car", "fuel", "petrol", "diesel", "bus", "train", "metro", "auto", "parking"], "i-cat-transport"],
  [["furnitur", "rental", "ikea", "sofa", "decor", "appliance", "fridge"], "i-cat-furniture"],
  [["shop", "amazon", "flipkart", "cloth", "apparel", "shoe", "slipper"], "i-cat-shopping"],
  [["health", "medic", "doctor", "pharma", "hospital", "medicine", "fitness", "gym"], "i-cat-health"],
  [["movie", "game", "music", "entertain", "netflix", "spotify", "subscription", "ott"], "i-cat-fun"],
  [["gift", "present", "donation"], "i-cat-gift"],
  [["educat", "school", "college", "course", "tuition", "book"], "i-cat-education"],
  [["pet", "dog"], "i-cat-pets"],
];
function catIconId(name) {
  const n = (name || "").toLowerCase();
  for (const [keys, id] of CAT_ICONS) if (keys.some((k) => n.includes(k))) return id;
  return "i-cat-other";
}
// signature icon tint per delivery/company category (mid-tones legible on light + dark)
const CAT_COLORS = [
  [["amazon"], "#f59e0b"],
  [["swiggy"], "#f97316"],
  [["zomato"], "#ef4444"],
  [["zepto"], "#8b5cf6"],
  [["blinkit"], "#eab308"],
  [["instamart"], "#ec4899"],
  [["flipkart"], "#2874f0"],
  [["pronto"], "#06b6d4"],
  [["furlenco"], "#6366f1"],
  [["rentomojo", "rentmojo"], "#14b8a6"],
  [["snabbit"], "#22c55e"],
  [["urbanclap"], "#a21caf"],
  [["rapido"], "#facc15"],
  [["uber"], "#64748b"],
];
function catColor(name) {
  const n = (name || "").toLowerCase();
  for (const [keys, c] of CAT_COLORS) if (keys.some((k) => n.includes(k))) return c;
  return "";
}
const catColorStyle = (name) => { const c = catColor(name); return c ? ` style="color:${c}"` : ""; };

const TAB_TITLE = { add: "Add expense", activity: "Activity", settle: "Settle up",
                    trends: "Trends", recurring: "Recurring", scratch: "Shared notes", settings: "Settings" };

// --- auth ------------------------------------------------------------------
function showLogin() { $("#login").hidden = false; $("#app").hidden = true; }
async function doLogin() {
  try {
    await api("/login", jbody({ body: { password: $("#pw").value } }));
    $("#login").hidden = true; $("#app").hidden = false; boot();
  } catch { $("#login-err").textContent = "That password didn't work."; }
}
$("#pw")?.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doLogin(); } });

// --- tabs ------------------------------------------------------------------
function buildTabbar() {
  const bar = $("#tabbar"); bar.innerHTML = "";
  $$("#tabs .tab-btn").forEach((b) => bar.appendChild(b.cloneNode(true)));
  $$(".tab-btn").forEach((b) => b.onclick = () => selectTab(b.dataset.tab));
}
function selectTab(name) {
  if (!TAB_TITLE[name]) name = "add";
  // guard against silently losing unsaved Settings edits
  if (CURRENT_TAB === "settings" && name !== "settings" && SETTINGS_DIRTY) {
    if (!confirm("You have unsaved changes in Settings. Leave without saving?")) return;
    SETTINGS_DIRTY = false;
  }
  CURRENT_TAB = name;
  $$(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  $$(".tab").forEach((t) => t.hidden = t.id !== "tab-" + name);
  $("#topbar-title").textContent = TAB_TITLE[name] || "";
  if (location.hash.slice(1) !== name) history.replaceState(null, "", "#" + name);
  $(".scroll").scrollTop = 0;
  ({ activity: loadActivity, settle: loadSettle, trends: loadTrends, recurring: loadRecurring,
     scratch: loadNotes, settings: loadSettings }[name] || (() => {}))();
}
const goTab = selectTab;
window.addEventListener("hashchange", () => { const h = location.hash.slice(1); if (TAB_TITLE[h]) selectTab(h); });

// --- boot ------------------------------------------------------------------
async function boot(bs) {
  if (!bs) bs = await api("/api/bootstrap");   // one round trip: settings + categories + balance
  CONFIG.ocr = !!bs.ocr;
  SETTINGS = bs.settings;
  buildTabbar();
  fillCategorySelects(bs.categories);
  buildSegmented($("#paidby-seg")); buildSegmented($("#rec-paidby-seg"));
  buildRangeSeg();
  wireOvQuick();
  $("#scan-btn").hidden = !CONFIG.ocr;
  // remember last category + payer
  const lc = ls.get("cf_last_cat"), lp = ls.get("cf_last_payer");
  if (lc && $("#cat-select").querySelector(`option[value="${lc}"]`)) $("#cat-select").value = lc;
  syncCatIcon();
  if (lp) setSeg($("#paidby-seg"), lp);
  $("#expense-form").date.value = new Date().toISOString().slice(0, 10);
  renderSplitStrip();
  renderBalance(bs.balance);
  const h = location.hash.slice(1);
  if (h && TAB_TITLE[h] && h !== "add") selectTab(h);
  // first-run: ledger still on seed defaults → guide setup (server-driven, so partner B won't re-see it)
  const fresh = SETTINGS.name1 === "Person 1" && SETTINGS.name2 === "Person 2";
  if (fresh && !ls.get("cf_onb_skip")) showOnboarding(); else $("#onboarding").hidden = true;
}

// --- first-run onboarding --------------------------------------------------
function showOnboarding() { $("#onboarding").hidden = false; onbRatio(); }
function skipOnboarding() { ls.set("cf_onb_skip", "1"); $("#onboarding").hidden = true; }
function onbRatio() {
  const f = $("#onb-form");
  $("#onb-chip-1").textContent = initial(f.name1.value, "A");
  $("#onb-chip-2").textContent = initial(f.name2.value, "B");
  const a = Math.round((f.income1.value || 0) * 100), b = Math.round((f.income2.value || 0) * 100), t = a + b;
  const hint = $("#onb-ratio-hint"), strip = $("#onb-split");
  if (t <= 0) { hint.hidden = false; strip.hidden = true; return; }
  const pa = Math.round(a / t * 100);
  hint.hidden = true; strip.hidden = false;
  $("#onb-split-a").style.width = pa + "%"; $("#onb-split-b").style.width = (100 - pa) + "%";
  $("#onb-split-legend").innerHTML =
    `<span><b>${pa}%</b> ${esc(f.name1.value || "you")}</span><span>${esc(f.name2.value || "partner")} <b>${100 - pa}%</b></span>`;
}
$("#onb-form")?.addEventListener("input", onbRatio);
async function saveOnboarding(e) {
  e.preventDefault(); const f = e.target;
  await api("/api/settings", jbody({ method: "PUT", body: {
    name1: f.name1.value, name2: f.name2.value,
    income1_paise: toPaise(f.income1.value), income2_paise: toPaise(f.income2.value),
    upi1: f.upi1.value, upi2: f.upi2.value } }));
  ls.set("cf_onb_skip", "1");
  $("#onboarding").hidden = true;
  await boot(); selectTab("add");
  return false;
}

// --- empty states ----------------------------------------------------------
function emptyState(icon, title, body, cta, label = "Add your first expense") {
  return `<div class="empty"><svg class="ic"><use href="#i-${icon}"/></svg>
    <div class="empty-title">${title}</div><div class="empty-body">${body}</div>
    ${cta ? `<button class="btn btn-primary btn-sm" onclick="${cta}">${label}</button>` : ""}</div>`;
}

// --- segmented "paid by" ---------------------------------------------------
function buildSegmented(el) {
  el.classList.add("seg-slide");
  el.dataset.sel = "1";
  el.innerHTML = [1, 2].map((p) =>
    `<button type="button" class="seg-opt${p === 1 ? " on" : ""}" data-p="${p}"><span class="mk"></span>${esc(person(p).n)}</button>`).join("")
    + `<span class="seg-thumb" aria-hidden="true"></span>`;
  el.querySelectorAll(".seg-opt").forEach((b) => b.onclick = () => setSeg(el, b.dataset.p));
}
function setSeg(el, p) {
  el.querySelectorAll(".seg-opt").forEach((x) => x.classList.toggle("on", x.dataset.p == p));
  el.dataset.sel = String(p);   // drives the sliding person-colored thumb
}
const segValue = (el) => +el.querySelector(".seg-opt.on").dataset.p;

// --- segmented "split" (income / 50:50 / custom) ---------------------------
function buildSplitSeg(segEl, form, ovRow) {
  const opts = [["ratio", "By income"], ["half", "50 : 50"], ["custom", "Custom"]];
  segEl.innerHTML = opts.map((o, i) =>
    `<button type="button" class="seg-opt${i === 0 ? " on" : ""}" data-s="${o[0]}">${o[1]}</button>`).join("");
  segEl.querySelectorAll(".seg-opt").forEach((b) => b.onclick = () => applySplit(segEl, form, ovRow, b.dataset.s));
}
function applySplit(segEl, form, ovRow, s) {
  segEl.querySelectorAll(".seg-opt").forEach((x) => x.classList.toggle("on", x.dataset.s === s));
  if (s === "ratio") { form.override_r1.value = ""; form.override_r2.value = ""; ovRow.hidden = true; }
  else if (s === "half") { form.override_r1.value = "1"; form.override_r2.value = "1"; ovRow.hidden = true; }
  else { ovRow.hidden = false; }
}
function setSplitFromOverride(segEl, form, ovRow, r1, r2) {
  let s = "custom";
  if (r1 == null || r2 == null || (r1 === "" )) s = "ratio";
  else if (+r1 === 1 && +r2 === 1) s = "half";
  applySplit(segEl, form, ovRow, s);
  if (s === "custom") { form.override_r1.value = r1; form.override_r2.value = r2; }
}
function wireOvQuick() {
  $$(".ov-quick").forEach((q) => {
    q.textContent = q.dataset.a === "100" ? "100% " + (SETTINGS.name1 || "A") : "100% " + (SETTINGS.name2 || "B");
    q.onclick = () => {
      const form = q.closest("form");
      form.override_r1.value = q.dataset.a; form.override_r2.value = q.dataset.b;
      const seg = $("#" + q.dataset.seg);
      if (seg.tagName === "SELECT") { seg.value = "custom"; $("#ov-custom").hidden = false; }
      else setSeg2(seg, "custom");
    };
  });
}
// Add-form split dropdown → clear/reveal the custom override row (edit modal keeps its segmented control)
function setSplitAdd(v) {
  const f = $("#expense-form"), ov = $("#ov-custom");
  if (v === "ratio") { f.override_r1.value = ""; f.override_r2.value = ""; ov.hidden = true; }
  else if (v === "half") { f.override_r1.value = "1"; f.override_r2.value = "1"; ov.hidden = true; }
  else ov.hidden = false;
}
const setSeg2 = (el, s) => el.querySelectorAll(".seg-opt").forEach((x) => x.classList.toggle("on", x.dataset.s === s));

// --- balance flow ----------------------------------------------------------
function flowHTML(b) {
  if (b.raw === 0) return `<div class="settled-badge"><svg class="ic"><use href="#i-check"/></svg> All square</div>`;
  const dP = b.raw > 0 ? 2 : 1, cP = b.raw > 0 ? 1 : 2, d = person(dP), c = person(cP);
  return `<div class="flow-people">
      <div class="flow-person">${avatarChip(dP)}<span class="who">${esc(d.n)}</span></div>
      <div class="flow-arrow" style="--c1:${d.color};--c2:${c.color};--head:${c.color}"></div>
      <div class="flow-person">${avatarChip(cP)}<span class="who">${esc(c.n)}</span></div>
    </div>
    <div class="flow-amt">${rs(b.balance_paise)}</div>
    <div class="flow-verb"><b>${esc(d.n)}</b> owes <b>${esc(c.n)}</b></div>`;
}
let LAST_BAL = null;
async function loadBalance() { renderBalance(await api("/api/balance")); }
function renderBalance(b) {
  LAST_BAL = b;
  $("#hero-balance").innerHTML = flowHTML(b);
  $("#settle-flow").innerHTML = flowHTML(b);
  const chip = $("#balance-chip");
  if (b.raw === 0) chip.innerHTML = `<span class="dot dot-a"></span><span class="dot dot-b"></span> All square`;
  else { const dP = b.raw > 0 ? 2 : 1;
    chip.innerHTML = `${avatarChip(dP, "chip", "width:16px;height:16px;font-size:9px")} owes <span class="amt">${rs0(b.balance_paise)}</span>`; }
  // settle controls
  $("#settle-controls").hidden = b.raw === 0;
  $("#settle-note").textContent = b.raw === 0
    ? "You're even — nothing to settle right now."
    : "Record a payback (full or partial); the balance updates instantly.";
  if (b.raw !== 0) $("#settle-amount").value = (b.balance_paise / 100).toFixed(2);
  // UPI button + QR/copy fallback — amount is driven by the settle box (partial-pay ready)
  const fb = $("#pay-fallback");
  if (b.pay) {
    fb.hidden = false;
    UPI_VPA = b.pay.vpa;
    $("#copy-upi").innerHTML = `<span class="vpa">${esc(b.pay.vpa)}</span><span class="copy-lbl">Copy</span>`;
    refreshPay();
  } else { $("#upi-btn").hidden = true; fb.hidden = true; PENDING = null; }
}

// how much to pay right now: the box amount, clamped to (0, balance] — never overpay
function payAmountPaise() {
  const b = LAST_BAL; if (!b) return 0;
  const v = $("#settle-amount").value;
  let amt = v ? toPaise(v) : b.balance_paise;
  if (!amt || amt <= 0) amt = b.balance_paise;
  return Math.min(amt, b.balance_paise);
}
function upiLink(vpa, name, paise) {
  return "upi://pay?" + new URLSearchParams(
    { pa: vpa, pn: name, am: (paise / 100).toFixed(2), cu: "INR", tn: "Couple Finance" }).toString();
}
// rebuild UPI button + QR + prompt amount from the current box value
function refreshPay() {
  const b = LAST_BAL, upi = $("#upi-btn");
  if (!b || !b.pay) { if (upi) upi.hidden = true; return; }
  const amt = payAmountPaise();
  const link = upiLink(b.pay.vpa, b.pay.name, amt);
  upi.hidden = false; upi.href = link;
  $("#upi-label").textContent = `Pay ${rs0(amt)} to ${b.pay.name} via UPI`;
  try { const q = qrcode(0, "M"); q.addData(link); q.make(); $("#upi-qr").src = q.createDataURL(4, 4); }
  catch { $("#upi-qr").removeAttribute("src"); }
  const from = b.raw > 0 ? 2 : 1, to = b.raw > 0 ? 1 : 2;
  upi.onclick = () => { PENDING = { amount_paise: payAmountPaise(), from, to, name: b.pay.name }; };
}
// sanitize the settle box to a valid amount and hard-cap it to what's owed
function onSettleAmountInput() {
  const b = LAST_BAL; if (!b) return;
  const el = $("#settle-amount");
  const cleaned = el.value.replace(/[^0-9.]/g, "").replace(/(\..*)\./g, "$1"); // digits + one dot only
  if (cleaned !== el.value) el.value = cleaned;
  if (el.value !== "" && toPaise(el.value) > b.balance_paise) el.value = (b.balance_paise / 100).toFixed(2);
  refreshPay();
}
$("#settle-amount")?.addEventListener("input", onSettleAmountInput);

// --- UPI copy + "did you pay?" prompt on return ----------------------------
let UPI_VPA = "", PENDING = null, WENT_HIDDEN = false;
async function copyUpi() {
  try { await navigator.clipboard.writeText(UPI_VPA); } catch {}
  const el = $("#copy-upi .copy-lbl"); if (el) { el.textContent = "Copied ✓"; setTimeout(() => (el.textContent = "Copy"), 1300); }
}
document.addEventListener("visibilitychange", () => {
  if (document.hidden) WENT_HIDDEN = true;
  else if (PENDING && WENT_HIDDEN) { showPayPrompt(); WENT_HIDDEN = false; }
});
function showPayPrompt() {
  if (!PENDING) return;
  $("#pay-prompt-title").textContent = `Did you pay ${PENDING.name} ${rs0(PENDING.amount_paise)}?`;
  $("#pay-prompt").hidden = false;
}
function dismissPayPrompt() { $("#pay-prompt").hidden = true; PENDING = null; }
async function confirmPayPrompt() {
  if (!PENDING) { $("#pay-prompt").hidden = true; return; }
  await api("/api/settlements", jbody({ body: {
    amount_paise: PENDING.amount_paise, from_person: PENDING.from, to_person: PENDING.to, note: "settle up (UPI)" } }));
  PENDING = null; $("#pay-prompt").hidden = true;
  await loadSettle();
}

async function loadSettle() { await loadBalance(); await loadSettlementHistory(); }

async function settleUp() {
  const b = LAST_BAL || await api("/api/balance");
  if (b.raw === 0) return;
  const amt = payAmountPaise();
  if (!amt || amt <= 0) return;
  const from = b.raw > 0 ? 2 : 1, to = b.raw > 0 ? 1 : 2;
  await api("/api/settlements", jbody({ body: { amount_paise: amt, from_person: from, to_person: to, note: "settle up" } }));
  await loadSettle();
  toast(`Settled ${rs0(amt)}`);
}

async function loadSettlementHistory() {
  const list = await api("/api/settlements");
  $("#settle-history-wrap").hidden = list.length === 0;
  $("#settle-history").innerHTML = list.map((x) => {
    const from = person(x.from_person), to = person(x.to_person);
    return `<div class="row">
      <span class="row-avatar" style="background:${from.color}"><svg class="ic" style="width:16px;height:16px"><use href="#i-check"/></svg></span>
      <div class="row-main"><div class="row-desc">${esc(from.n)} paid ${esc(to.n)}</div>
        <div class="row-meta">${fmtDate(x.date)}${x.note ? " · " + esc(x.note) : ""}</div></div>
      <div class="row-right"><div class="row-amt">${rs0(x.amount_paise)}</div></div>
      <button class="row-del" onclick="delSettlement(${x.id})" aria-label="Undo"><svg class="ic"><use href="#i-trash"/></svg></button>
    </div>`;
  }).join("");
}
async function delSettlement(id) {
  if (!confirm("Undo this settlement?")) return;
  await api("/api/settlements/" + id, { method: "DELETE" }); await loadSettle();
}

// --- add expense -----------------------------------------------------------
async function addExpense(e) {
  e.preventDefault();
  const f = e.target;
  await api("/api/expenses", jbody({ body: {
    description: f.description.value, amount_paise: toPaise(f.amount.value),
    category_id: +f.category_id.value, paid_by: segValue($("#paidby-seg")),
    date: f.date.value || undefined,
    override_r1: f.override_r1.value !== "" ? +f.override_r1.value : null,
    override_r2: f.override_r2.value !== "" ? +f.override_r2.value : null,
  } }));
  ls.set("cf_last_cat", f.category_id.value); ls.set("cf_last_payer", segValue($("#paidby-seg")));
  f.reset(); f.date.value = new Date().toISOString().slice(0, 10);
  const lc = ls.get("cf_last_cat");
  if (lc && $("#cat-select").querySelector(`option[value="${lc}"]`)) $("#cat-select").value = lc;
  syncCatIcon();
  $("#split-sel").value = "ratio"; $("#ov-custom").hidden = true;
  setSeg($("#paidby-seg"), ls.get("cf_last_payer") || 1);
  $("#scan-status").hidden = true;
  await loadBalance();
  flash(f.querySelector('button[type="submit"]'), "Added ✓");
  toast("Expense added");
}
function flash(btn, txt) { const t = btn.textContent; btn.textContent = txt; setTimeout(() => (btn.textContent = t), 1100); }

// --- receipt OCR -----------------------------------------------------------
async function scanReceipt(input) {
  const file = input.files[0]; if (!file) return;
  const st = $("#scan-status"); st.hidden = false; st.className = "scan-status loading"; st.textContent = "Reading receipt…";
  try {
    const fd = new FormData(); fd.append("image", file);
    const r = await fetch("/api/ocr", { method: "POST", body: fd, credentials: "same-origin" });
    if (!r.ok) throw new Error();
    const j = await r.json();
    const f = $("#expense-form");
    if (j.amount_paise) f.amount.value = (j.amount_paise / 100).toFixed(2);
    if (j.merchant && !f.description.value) f.description.value = j.merchant;
    st.className = "scan-status ok";
    st.textContent = j.amount_paise ? `Found ${rs(j.amount_paise)} — check the details and save` : "Couldn't read a total — enter it manually";
  } catch { st.className = "scan-status err"; st.textContent = "Scan failed — enter the expense manually"; }
  input.value = "";
}

// --- activity feed ---------------------------------------------------------
async function loadActivity() {
  const items = await api("/api/activity?days=120");
  ACT_BY_ID = {};
  items.forEach((x) => { if (x.type === "expense") ACT_BY_ID[x.id] = x; });
  $("#activity-list").innerHTML = items.length
    ? items.map((x) => x.type === "settlement" ? settlementRow(x) : expenseRow(x)).join("")
    : emptyState("activity", "No expenses yet", "Everything you both spend shows up here, split automatically by your income ratio.", "goTab('add')");
}
function expenseRow(x) {
  const to = x.paid_to ? ` · <span class="tag">→ ${esc(x.paid_to)}</span>` : "";
  const ov = x.override_r1 != null ? ` · ${x.override_r1}:${x.override_r2}` : "";
  const cat = x.category || "—";
  return `<div class="row row-tap" onclick="openEdit(${x.id})">
    ${avatarChip(x.paid_by, "row-avatar")}
    <div class="row-main">
      <div class="row-desc">${esc(x.description)}</div>
      <div class="row-meta"><svg class="cat-ic"${catColorStyle(cat)}><use href="#${catIconId(cat)}"/></svg>${fmtDate(x.date)} · ${esc(cat)}${to}${ov}</div>
    </div>
    <div class="row-right"><div class="row-amt">${rs0(x.amount_paise)}</div>
      <div class="row-shares">${person(1).letter} ${rs0(x.share1_paise)} · ${person(2).letter} ${rs0(x.share2_paise)}</div></div>
    <span class="row-edit"><svg class="ic"><use href="#i-edit"/></svg></span>
  </div>`;
}
function settlementRow(x) {
  const from = person(x.from_person), to = person(x.to_person);
  return `<div class="row row-settle">
    <span class="row-avatar settle-avatar"><svg class="ic" style="width:16px;height:16px"><use href="#i-check"/></svg></span>
    <div class="row-main"><div class="row-desc">${esc(from.n)} paid ${esc(to.n)}</div>
      <div class="row-meta">${fmtDate(x.date)} · settled up</div></div>
    <div class="row-right"><div class="row-amt settle-amt-txt">${rs0(x.amount_paise)}</div></div>
  </div>`;
}
async function delExpense(id) {
  if (!confirm("Delete this expense?")) return;
  await api("/api/expenses/" + id, { method: "DELETE" });
  closeEdit(); await loadActivity(); await loadBalance();
}

// --- edit modal ------------------------------------------------------------
function openEdit(id) {
  const x = ACT_BY_ID[id]; if (!x) return;
  const f = $("#edit-form");
  buildSegmented($("#edit-paidby-seg"));
  buildSplitSeg($("#edit-split-seg"), f, $("#edit-ov"));
  f.id.value = x.id;
  f.amount.value = (x.amount_paise / 100).toFixed(2);
  f.description.value = x.description;
  f.category_id.value = x.category_id || "";
  f.paid_to.value = x.paid_to || "";
  f.date.value = x.date;
  setSeg($("#edit-paidby-seg"), x.paid_by);
  setSplitFromOverride($("#edit-split-seg"), f, $("#edit-ov"),
    x.override_r1 == null ? "" : x.override_r1, x.override_r2 == null ? "" : x.override_r2);
  $("#edit-modal").hidden = false;
}
function closeEdit() { $("#edit-modal").hidden = true; }
async function saveEdit(e) {
  e.preventDefault();
  const f = e.target;
  await api("/api/expenses/" + f.id.value, jbody({ method: "PUT", body: {
    date: f.date.value, description: f.description.value, amount_paise: toPaise(f.amount.value),
    category_id: +f.category_id.value, paid_by: segValue($("#edit-paidby-seg")), paid_to: f.paid_to.value,
    override_r1: f.override_r1.value !== "" ? +f.override_r1.value : null,
    override_r2: f.override_r2.value !== "" ? +f.override_r2.value : null,
  } }));
  closeEdit(); await loadActivity(); await loadBalance();
}
function deleteFromEdit() { delExpense($("#edit-form").id.value); }

// --- trends ----------------------------------------------------------------
let RANGE = 6;
function buildRangeSeg() {
  const el = $("#range-seg");
  el.innerHTML = [3, 6, 12].map((m) =>
    `<button type="button" class="seg-opt${m === RANGE ? " on" : ""}" data-m="${m}">${m}m</button>`).join("");
  el.querySelectorAll(".seg-opt").forEach((b) => b.onclick = () => {
    RANGE = +b.dataset.m; el.querySelectorAll(".seg-opt").forEach((x) => x.classList.toggle("on", x === b)); loadTrends();
  });
}
// spend-history: pick a top category, chart its monthly spend (Rufus-style area/line)
let HIST_CAT = null, HIST_DATA = null;

function sparkSvg(series, months, color) {
  const W = 340, H = 150, pL = 42, pR = 14, pT = 16, pB = 26;
  const plotW = W - pL - pR, plotH = H - pT - pB, base = pT + plotH;
  const n = series.length, max = Math.max(1, ...series);
  const xAt = (i) => n <= 1 ? pL + plotW / 2 : pL + (i * plotW) / (n - 1);
  const yAt = (v) => pT + (1 - v / max) * plotH;
  const pts = series.map((v, i) => [xAt(i), yAt(v)]);
  const line = pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" ");
  const area = n <= 1 ? "" : `${line} L ${xAt(n - 1).toFixed(1)} ${base} L ${xAt(0).toFixed(1)} ${base} Z`;
  const grid = [pT, pT + plotH / 2, base].map((y) =>
    `<line x1="${pL}" y1="${y}" x2="${W - pR}" y2="${y}" class="spark-grid" vector-effect="non-scaling-stroke"/>`).join("");
  const yLbls = `<text x="${pL - 6}" y="${pT + 3}" class="spark-ax" text-anchor="end">${rs0(max)}</text>
    <text x="${pL - 6}" y="${base + 3}" class="spark-ax" text-anchor="end">₹0</text>`;
  const step = n > 6 ? 2 : 1;
  const xLbls = months.map((m, i) => (i % step === 0 || i === n - 1)
    ? `<text x="${xAt(i).toFixed(1)}" y="${H - 8}" class="spark-ax" text-anchor="middle">${mLabel(m.month)}</text>` : "").join("");
  const last = pts[n - 1], cur = rs0(series[n - 1]);
  const dot = `<circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="4" style="fill:${color}" class="spark-dot"/>`;
  const bw = 12 + cur.length * 6.4, bx = Math.max(pL, Math.min(W - pR - bw, last[0] - bw / 2));
  const by = last[1] < pT + 24 ? last[1] + 8 : last[1] - 25;
  const callout = `<rect x="${bx.toFixed(1)}" y="${by.toFixed(1)}" width="${bw.toFixed(1)}" height="18" rx="6" style="fill:${color}"/>
    <text x="${(bx + bw / 2).toFixed(1)}" y="${(by + 12.6).toFixed(1)}" class="spark-cur" text-anchor="middle">${cur}</text>`;
  return `<svg class="spark" viewBox="0 0 ${W} ${H}" role="img" aria-label="Monthly spend chart">
    ${grid}${yLbls}
    ${area ? `<path d="${area}" style="fill:${color};fill-opacity:.14"/>` : ""}
    <path d="${line}" style="stroke:${color}" class="spark-line" vector-effect="non-scaling-stroke"/>
    ${dot}${xLbls}${callout}</svg>`;
}

function histCardHTML() {
  if (!HIST_DATA) return "";
  const { cats, months } = HIST_DATA;
  const top = [...cats].sort((a, b) => b.count - a.count).filter((c) => c.count > 0).slice(0, 5);
  if (!top.length) return "";
  if (!top.some((c) => c.category === HIST_CAT)) HIST_CAT = top[0].category;
  const sel = top.find((c) => c.category === HIST_CAT);
  const color = catColor(sel.category) || "var(--a)";
  const s = sel.series, cur = s[s.length - 1], mn = Math.min(...s), mx = Math.max(...s);
  const pills = top.map((c) => {
    const pc = catColor(c.category) || "var(--a)";
    return `<button type="button" class="hist-pill${c.category === sel.category ? " on" : ""}" data-cat="${esc(c.category)}" style="--pc:${pc}">
      <svg class="cat-ic" style="color:${pc}"><use href="#${catIconId(c.category)}"/></svg>${esc(c.category)}</button>`;
  }).join("");
  const header = `Over the past ${RANGE} months, your <b style="color:${color}">${esc(sel.category)}</b> spend ranged <b>${rs0(mn)}</b>–<b>${rs0(mx)}</b> · this month <b>${rs0(cur)}</b>.`;
  return `<div class="chart-card hist-card" id="hist-card">
    <div class="chart-title">Spend history</div>
    <div class="hist-pills">${pills}</div>
    <div class="hist-head">${header}</div>
    ${sparkSvg(sel.series, months, color)}</div>`;
}

function wireHistPills() {
  document.querySelectorAll(".hist-pill").forEach((b) => b.onclick = () => {
    HIST_CAT = b.dataset.cat;
    const el = $("#hist-card"); if (el) { el.outerHTML = histCardHTML(); wireHistPills(); }
  });
}

async function loadTrends() {
  const d = await api("/api/analytics?months=" + RANGE);
  HIST_DATA = { cats: d.by_category, months: d.months };
  const maxM = Math.max(1, ...d.months.map((m) => m.total_paise));
  const totalRange = d.months.reduce((s, m) => s + m.total_paise, 0);
  const sum1 = d.months.reduce((s, m) => s + m.share1_paise, 0);
  const sum2 = d.months.reduce((s, m) => s + m.share2_paise, 0);

  // stacked monthly bars (A share teal / B share orange)
  const bars = d.months.map((m) => {
    const h = m.total_paise / maxM * 100;
    const a = m.total_paise ? m.share1_paise / m.total_paise * h : 0;
    return `<div class="bar-col" title="${mLabel(m.month)}: ${rs0(m.total_paise)}">
      <div class="bar-val">${m.total_paise ? rs0(m.total_paise) : ""}</div>
      <div class="bar-stack"><div class="bar-b" style="height:${(h - a).toFixed(1)}%"></div><div class="bar-a" style="height:${a.toFixed(1)}%"></div></div>
      <div class="bar-lbl">${mLabel(m.month)}</div></div>`;
  }).join("");

  const maxCat = Math.max(1, ...d.by_category.map((c) => c.amount_paise));
  const cats = d.by_category.map((c) => `<div class="cat-line">
      <span class="nm">${esc(c.category)}</span>
      <span class="track"><span class="fill" style="width:${(c.amount_paise / maxCat * 100).toFixed(1)}%"></span></span>
      <span class="val">${rs0(c.amount_paise)}</span></div>`).join("");

  $("#trends-box").innerHTML = `
    <div class="totals-total">
      <div class="lbl">Spent over ${RANGE} months</div>
      <div class="big num">${rs0(totalRange)}</div>
      <div class="person-split">
        <div><span class="leg-dot" style="background:var(--a)"></span>${esc(d.name1)}<span class="v">${rs0(sum1)}</span></div>
        <div><span class="leg-dot" style="background:var(--b)"></span>${esc(d.name2)}<span class="v">${rs0(sum2)}</span></div>
      </div>
    </div>
    <div class="chart-card">
      <div class="chart-title">Monthly spend</div>
      <div class="bar-chart">${bars}</div>
    </div>
    ${histCardHTML()}
    <div class="cat-block">${cats || emptyState("trends", "No spending yet", "Once you log expenses they'll chart here by month, person, and category.", "goTab('add')")}</div>`;
  wireHistPills();
}

// --- recurring -------------------------------------------------------------
async function addRecurring(e) {
  e.preventDefault(); const f = e.target;
  await api("/api/recurring", jbody({ body: {
    description: f.description.value, amount_paise: toPaise(f.amount.value),
    category_id: +f.category_id.value, paid_by: segValue($("#rec-paidby-seg")),
    paid_to: f.paid_to.value, day_of_month: +f.day_of_month.value } }));
  f.reset(); f.day_of_month.value = 1; loadRecurring();
}
async function loadRecurring() {
  const items = await api("/api/recurring");
  $("#rec-list").innerHTML = items.length ? items.map((r) => {
    const p = person(r.paid_by);
    return `<div class="row">${avatarChip(r.paid_by, "row-avatar")}
      <div class="row-main"><div class="row-desc">${esc(r.description)}</div>
        <div class="row-meta">Day ${r.day_of_month} · ${esc(p.n)}${r.paid_to ? " · <span class='tag'>→ " + esc(r.paid_to) + "</span>" : ""}</div></div>
      <div class="row-right"><div class="row-amt">${rs0(r.amount_paise)}</div><div class="row-shares">monthly</div></div>
      <button class="row-del" onclick="delRecurring(${r.id})" aria-label="Delete"><svg class="ic"><use href="#i-trash"/></svg></button></div>`;
  }).join("") : `<div class="empty"><svg class="ic"><use href="#i-recurring"/></svg><div class="empty-title">No recurring expenses</div><div class="empty-body">Add rent, Wi-Fi, or anything that repeats — it posts automatically each month.</div></div>`;
}
async function delRecurring(id) {
  if (!confirm("Delete this recurring expense?")) return;
  await api("/api/recurring/" + id, { method: "DELETE" }); loadRecurring();
}

// --- notes (multiple, minimal) ---------------------------------------------
let scratchTimer, CUR_NOTE = null, NOTES = [];
const CL_RE = /^(\s*)- \[( |x)\]\s?(.*)$/;   // checklist line: - [ ] text  /  - [x] text
const stripTitle = (c) => { const l = (c || "").split("\n").find((x) => x.trim()); return l ? l.trim() : ""; };
function noteTitle(c) {
  const t = stripTitle(c); if (!t) return "New note";
  const m = t.match(CL_RE); return (m ? m[3] : t).slice(0, 60) || "Checklist";
}
function notePreview(c) {
  return (c || "").split("\n").slice(1).map((x) => {
    const m = x.match(CL_RE); return m ? (m[2] === "x" ? "☑ " : "☐ ") + m[3] : x.trim();
  }).filter(Boolean).join("  ").slice(0, 80);
}
function showNotesList() { $("#notes-editor-view").hidden = true; $("#notes-list-view").hidden = false; }
async function loadNotes() {
  showNotesList();
  NOTES = await api("/api/notes");
  renderNotesList();
}
function renderNotesList() {
  const q = ($("#notes-search").value || "").toLowerCase().trim();
  const list = q ? NOTES.filter((n) => (n.content || "").toLowerCase().includes(q)) : NOTES;
  $("#notes-list").innerHTML = list.length ? list.map((n) => {
    const prev = notePreview(n.content);
    return `<button type="button" class="note-card${n.pinned ? " pinned" : ""}" onclick="openNote(${n.id})">
      <div class="note-title">${n.pinned ? '<svg class="ic pin-mark"><use href="#i-pin"/></svg>' : ""}${esc(noteTitle(n.content))}</div>
      <div class="note-sub"><span class="note-prev">${esc(prev || (n.content.trim() ? "" : "Empty note"))}</span><span class="note-date">${fmtDate((n.updated_at || "").slice(0, 10))}</span></div>
    </button>`;
  }).join("") : (q ? `<div class="empty"><div class="empty-title">No matches</div></div>`
    : emptyState("notes", "No notes yet", "Keep separate notes for trips, shopping lists, reminders — anything you two share.", "newNote()", "New note"));
}
async function newNote() {
  const { id } = await api("/api/notes", { method: "POST" });
  NOTES.unshift({ id, content: "", updated_at: new Date().toISOString(), pinned: 0 });
  openNote(id, true);
}
function openNote(id) {
  const n = NOTES.find((x) => x.id === id);
  if (!n) return loadNotes();
  CUR_NOTE = id;
  $("#scratch").value = n.content || "";
  $("#scratch-status").textContent = "";
  updatePinBtn();
  renderChecklist();
  $("#notes-list-view").hidden = true; $("#notes-editor-view").hidden = false;
  $("#scratch").focus();
}
function curNote() { return NOTES.find((x) => x.id === CUR_NOTE); }
function updatePinBtn() { const n = curNote(); $("#pin-btn").classList.toggle("on", !!(n && n.pinned)); }
async function backToNotes() { clearTimeout(scratchTimer); await saveNoteNow(); CUR_NOTE = null; loadNotes(); }
async function saveNoteNow() {
  const n = curNote(); if (!n) return;
  n.content = $("#scratch").value;
  await api("/api/notes/" + n.id, jbody({ method: "PUT", body: { content: n.content } }));
}
async function togglePin() {
  const n = curNote(); if (!n) return;
  n.pinned = n.pinned ? 0 : 1;
  updatePinBtn();
  await api("/api/notes/" + n.id, jbody({ method: "PUT", body: { pinned: !!n.pinned } }));
  toast(n.pinned ? "Pinned" : "Unpinned");
}
async function deleteCurrentNote() {
  if (CUR_NOTE == null) return;
  if (!confirm("Delete this note?")) return;
  clearTimeout(scratchTimer);
  await api("/api/notes/" + CUR_NOTE, { method: "DELETE" });
  NOTES = NOTES.filter((x) => x.id !== CUR_NOTE); CUR_NOTE = null;
  loadNotes(); toast("Note deleted");
}
// checklist: render tappable boxes for "- [ ] / - [x]" lines
function renderChecklist() {
  const lines = ($("#scratch").value || "").split("\n");
  const items = lines.map((l, i) => [i, l.match(CL_RE)]).filter(([, m]) => m);
  const panel = $("#checklist-panel");
  if (!items.length) { panel.hidden = true; panel.innerHTML = ""; return; }
  panel.hidden = false;
  panel.innerHTML = items.map(([i, m]) =>
    `<label class="cl-item${m[2] === "x" ? " done" : ""}"><input type="checkbox" ${m[2] === "x" ? "checked" : ""} onchange="toggleChecklist(${i})"><span>${esc(m[3]) || "Item"}</span></label>`).join("");
}
function toggleChecklist(i) {
  const lines = $("#scratch").value.split("\n");
  const m = lines[i].match(CL_RE); if (!m) return;
  lines[i] = `${m[1]}- [${m[2] === "x" ? " " : "x"}] ${m[3]}`;
  $("#scratch").value = lines.join("\n");
  renderChecklist();
  queueNoteSave();
}
function insertChecklistItem() {
  const ta = $("#scratch");
  const v = ta.value;
  ta.value = v + (v && !v.endsWith("\n") ? "\n" : "") + "- [ ] ";
  ta.focus();
  renderChecklist(); queueNoteSave();
}
function queueNoteSave() {
  if (CUR_NOTE == null) return;
  clearTimeout(scratchTimer); $("#scratch-status").textContent = "Saving…";
  scratchTimer = setTimeout(async () => { await saveNoteNow(); $("#scratch-status").textContent = "Saved"; }, 600);
}
$("#scratch")?.addEventListener("input", () => { renderChecklist(); queueNoteSave(); });
// Enter on a "- [ ] " line auto-continues the checklist
$("#scratch")?.addEventListener("keydown", (e) => {
  if (e.key !== "Enter") return;
  const ta = e.target, pos = ta.selectionStart;
  const before = ta.value.slice(0, pos), curLine = before.slice(before.lastIndexOf("\n") + 1);
  const m = curLine.match(CL_RE);
  if (m && m[3].trim()) {
    e.preventDefault();
    const ins = "\n- [ ] ";
    ta.value = before + ins + ta.value.slice(pos);
    ta.selectionStart = ta.selectionEnd = pos + ins.length;
    renderChecklist(); queueNoteSave();
  }
});

// --- settings --------------------------------------------------------------
function renderSplitStrip() {
  const a = SETTINGS.income1_paise || 0, b = SETTINGS.income2_paise || 0, t = a + b;
  if (t <= 0) { $("#split-strip").hidden = true; return; }
  const pa = Math.round(a / t * 100);
  $("#split-strip").hidden = false;
  $("#split-a").style.width = pa + "%"; $("#split-b").style.width = (100 - pa) + "%";
  $("#split-legend").innerHTML = `<span><b>${pa}%</b> ${esc(SETTINGS.name1)}</span><span>${esc(SETTINGS.name2)} <b>${100 - pa}%</b></span>`;
}
async function loadSettings() {
  const s = SETTINGS = await api("/api/settings");
  const f = $("#settings-form");
  f.name1.value = s.name1; f.name2.value = s.name2;
  f.income1.value = s.income1_paise / 100; f.income2.value = s.income2_paise / 100;
  f.upi1.value = s.upi1 || ""; f.upi2.value = s.upi2 || "";
  updateUpiHint(f.upi1); updateUpiHint(f.upi2);
  renderAvatarButtons();
  updateRatioPreview();
  SETTINGS_DIRTY = false;
  const cats = await api("/api/categories");
  $("#cat-manage").innerHTML = cats.map((c) =>
    `<span class="cat-tag"><svg class="cat-ic"${catColorStyle(c.name)}><use href="#${catIconId(c.name)}"/></svg>${esc(c.name)}<button onclick="delCategory(${c.id})" aria-label="Remove">×</button></span>`).join("");
}

// --- couple photos (avatars) -----------------------------------------------
function renderAvatarButtons() {
  [1, 2].forEach((p) => {
    const pr = person(p), btn = $("#av-" + p); if (!btn) return;
    if (pr.photo) { btn.classList.add("has-photo"); btn.style.backgroundImage = `url('${pr.photo}')`; btn.textContent = ""; }
    else { btn.classList.remove("has-photo"); btn.style.backgroundImage = ""; btn.textContent = pr.letter; }
    const rm = $("#av-rm-" + p); if (rm) rm.hidden = !pr.photo;
  });
}
function pickAvatar(p) { $("#av-in-" + p).click(); }
function onAvatarPick(p, input) {
  const f = input.files[0]; input.value = ""; if (!f) return;
  const img = new Image();
  img.onload = async () => {
    const S = 128, cv = document.createElement("canvas"); cv.width = cv.height = S;
    const ctx = cv.getContext("2d");
    const m = Math.min(img.width, img.height), sx = (img.width - m) / 2, sy = (img.height - m) / 2;
    ctx.drawImage(img, sx, sy, m, m, 0, 0, S, S);
    const data = cv.toDataURL("image/jpeg", 0.82);
    URL.revokeObjectURL(img.src);
    await api("/api/avatar", jbody({ method: "PUT", body: { person: p, image: data } }));
    SETTINGS["avatar" + p] = data; renderAvatarButtons(); if (LAST_BAL) renderBalance(LAST_BAL);
    toast("Photo updated");
  };
  img.onerror = () => toast("Couldn't read that image", "err");
  img.src = URL.createObjectURL(f);
}
async function removeAvatar(p) {
  await api("/api/avatar", jbody({ method: "PUT", body: { person: p, image: null } }));
  SETTINGS["avatar" + p] = null; renderAvatarButtons(); if (LAST_BAL) renderBalance(LAST_BAL);
  toast("Photo removed");
}
$("#settings-form")?.addEventListener("input", () => { SETTINGS_DIRTY = true; updateRatioPreview(); });
window.addEventListener("beforeunload", (e) => { if (SETTINGS_DIRTY) { e.preventDefault(); e.returnValue = ""; } });
function updateRatioPreview() {
  const f = $("#settings-form");
  const a = Math.round((f.income1.value || 0) * 100), b = Math.round((f.income2.value || 0) * 100), t = a + b;
  $("#ratio-preview").innerHTML = t > 0
    ? `Split ratio &nbsp;<b>${Math.round(a / t * 100)} : ${Math.round(b / t * 100)}</b>&nbsp; (${esc(f.name1.value || "A")} : ${esc(f.name2.value || "B")})` : "";
}
async function saveSettings(e) {
  e.preventDefault(); const f = e.target;
  await api("/api/settings", jbody({ method: "PUT", body: {
    name1: f.name1.value, name2: f.name2.value,
    income1_paise: toPaise(f.income1.value), income2_paise: toPaise(f.income2.value),
    upi1: f.upi1.value, upi2: f.upi2.value } }));
  SETTINGS_DIRTY = false;
  await boot(); flash(f.querySelector('button[type="submit"]'), "Saved ✓");
  toast("Settings saved");
}
async function fillCategorySelects(cats) {
  if (!cats) cats = await api("/api/categories");
  const opts = cats.map((c) => `<option value="${c.id}">${esc(c.name)}</option>`).join("");
  $("#cat-select").innerHTML = opts; $("#rec-cat").innerHTML = opts; $("#edit-cat").innerHTML = opts;
  buildCatPicker(cats);
  return cats;
}
// --- Add-form icon category picker (drives the hidden #cat-select value store) ---
function buildCatPicker(cats) {
  $("#cat-pop").innerHTML = cats.map((c) =>
    `<button type="button" class="cat-tile" role="option" data-id="${c.id}" aria-label="${esc(c.name)}" onclick="pickCat(${c.id})">
      <svg class="cat-ic"${catColorStyle(c.name)}><use href="#${catIconId(c.name)}"/></svg><span>${esc(c.name)}</span></button>`).join("");
  if (!$("#cat-select").value && cats[0]) $("#cat-select").value = cats[0].id;
  syncCatIcon();
}
function toggleCatPop() {
  const pop = $("#cat-pop"), open = pop.hidden;
  pop.hidden = !open;
  $("#cat-btn").setAttribute("aria-expanded", String(open));
}
function pickCat(id) {
  $("#cat-select").value = id;
  syncCatIcon();
  $("#cat-pop").hidden = true;
  $("#cat-btn").setAttribute("aria-expanded", "false");
}
function syncCatIcon() {
  const sel = $("#cat-select"), opt = sel.options[sel.selectedIndex], name = opt ? opt.textContent : "";
  $("#cat-btn-ic").querySelector("use").setAttribute("href", "#" + catIconId(name));
  $("#cat-btn-ic").style.color = catColor(name) || "";
  $("#cat-btn").setAttribute("aria-label", name ? "Category: " + name : "Category");
  $$("#cat-pop .cat-tile").forEach((t) => t.classList.toggle("on", t.dataset.id === sel.value));
}
// close the category popover on an outside click
document.addEventListener("click", (e) => {
  const pop = $("#cat-pop");
  if (pop && !pop.hidden && !e.target.closest(".cat-pick")) { pop.hidden = true; $("#cat-btn").setAttribute("aria-expanded", "false"); }
});
async function addCategory(e) {
  e.preventDefault();
  await api("/api/categories", jbody({ body: { name: e.target.name.value } }));
  e.target.reset(); await fillCategorySelects(); loadSettings();
}
async function delCategory(id) {
  await api("/api/categories/" + id, { method: "DELETE" }); await fillCategorySelects(); loadSettings();
}

// --- UPI ID format check (soft: recognise popular apps, warn only if malformed) ---
const UPI_HANDLES = {
  okhdfcbank: "Google Pay", okaxis: "Google Pay", okicici: "Google Pay", oksbi: "Google Pay", okhdfc: "Google Pay",
  ybl: "PhonePe", ibl: "PhonePe", axl: "PhonePe",
  paytm: "Paytm", ptaxis: "Paytm", ptsbi: "Paytm", pthdfc: "Paytm", ptyes: "Paytm", ptibl: "Paytm",
  superyes: "super.money", super: "super.money",
  apl: "Amazon Pay", yapl: "Amazon Pay",
  waaxis: "WhatsApp Pay", wahdfcbank: "WhatsApp Pay", waicici: "WhatsApp Pay", wasbi: "WhatsApp Pay",
  axisb: "CRED", ikwik: "Mobikwik", sliceaxis: "slice", fam: "FamPay", jupiteraxis: "Jupiter", naviaxis: "Navi",
  upi: "BHIM", sbi: "SBI", hdfcbank: "HDFC Bank", icici: "ICICI Bank", axisbank: "Axis Bank",
  yesbank: "Yes Bank", kotak: "Kotak", pnb: "PNB", idfcbank: "IDFC First", indianbank: "Indian Bank",
};
function upiInfo(v) {
  v = (v || "").trim();
  if (!v) return { state: "empty" };
  const m = v.match(/^[a-zA-Z0-9.\-_]+@([a-zA-Z][a-zA-Z0-9.\-]{1,})$/);
  if (!m) return { state: "bad" };
  return { state: "ok", provider: UPI_HANDLES[m[1].toLowerCase()] || null };
}
function updateUpiHint(inp) {
  const hint = inp.nextElementSibling && inp.nextElementSibling.classList.contains("upi-hint") ? inp.nextElementSibling : null;
  if (!hint) return;
  const i = upiInfo(inp.value);
  if (i.state === "empty") { hint.textContent = ""; hint.className = "upi-hint"; }
  else if (i.state === "bad") { hint.textContent = "⚠ A UPI ID looks like name@bank"; hint.className = "upi-hint bad"; }
  else if (i.provider) { hint.textContent = `✓ ${i.provider} UPI ID`; hint.className = "upi-hint ok"; }
  else { hint.textContent = "✓ Looks like a valid UPI ID"; hint.className = "upi-hint muted"; }
}
document.addEventListener("input", (e) => {
  if (e.target.matches && e.target.matches('input[name="upi1"],input[name="upi2"]')) updateUpiHint(e.target);
});

// --- export ----------------------------------------------------------------
function exportCsv() {
  const days = $("#export-range").value;
  const set = $("#export-settlements").checked ? "&settlements=1" : "";
  window.location = `/api/export?days=${days}${set}`;
}

// --- start -----------------------------------------------------------------
applyTheme();
(async () => {
  try {
    const bs = await api("/api/bootstrap");   // authed → one call gets everything; 401 → showLogin
    $("#app").hidden = false; boot(bs);
  } catch { showLogin(); }
})();
