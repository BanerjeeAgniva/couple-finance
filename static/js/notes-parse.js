// Note text parsing: title, preview, and checklist-line detection. Pure; no DOM.

export const CL_RE = /^(\s*)- \[( |x)\]\s?(.*)$/;   // checklist line: - [ ] text  /  - [x] text

export const stripTitle = (c) => { const l = (c || "").split("\n").find((x) => x.trim()); return l ? l.trim() : ""; };

export function noteTitle(c) {
  const t = stripTitle(c); if (!t) return "New note";
  const m = t.match(CL_RE); return (m ? m[3] : t).slice(0, 60) || "Checklist";
}

export function notePreview(c) {
  return (c || "").split("\n").slice(1).map((x) => {
    const m = x.match(CL_RE); return m ? (m[2] === "x" ? "☑ " : "☐ ") + m[3] : x.trim();
  }).filter(Boolean).join("  ").slice(0, 80);
}
