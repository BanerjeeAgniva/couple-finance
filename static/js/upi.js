// UPI helpers: intent-link builder + soft VPA validation. Pure; no DOM.

export function upiLink(vpa, name, paise) {
  return "upi://pay?" + new URLSearchParams(
    { pa: vpa, pn: name, am: (paise / 100).toFixed(2), cu: "INR", tn: "Couple Finance" }).toString();
}

// popular UPI handles → human provider name (soft recognition; warn only if malformed)
export const UPI_HANDLES = {
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
export function upiInfo(v) {
  v = (v || "").trim();
  if (!v) return { state: "empty" };
  const m = v.match(/^[a-zA-Z0-9.\-_]+@([a-zA-Z][a-zA-Z0-9.\-]{1,})$/);
  if (!m) return { state: "bad" };
  return { state: "ok", provider: UPI_HANDLES[m[1].toLowerCase()] || null };
}
