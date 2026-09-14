// Pure formatting / parsing helpers — no DOM, no app state. Reusable & testable.

export const rs = (p) => "₹" + (p / 100).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const rs0 = (p) => "₹" + Math.round(p / 100).toLocaleString("en-IN");
export const toPaise = (r) => Math.round(parseFloat(r) * 100);
export const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
export const mLabel = (k) => new Date(k + "-01T00:00").toLocaleDateString("en-IN", { month: "short" });
export const jbody = (o) => ({ method: o.method || "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(o.body) });
export const fmtDate = (iso) => { const d = new Date(iso + "T00:00"); return isNaN(d) ? iso : d.toLocaleDateString("en-IN", { day: "numeric", month: "short" }); };
export const initial = (name, fb) => { const t = (name || "").trim(); return t ? t[0].toUpperCase() : fb; };
