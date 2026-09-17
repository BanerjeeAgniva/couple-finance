// Pure SVG builder for the spend-history sparkline. No DOM, no app state.
import { rs0, mLabel } from "./format.js";

export function sparkSvg(series, months, color) {
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
