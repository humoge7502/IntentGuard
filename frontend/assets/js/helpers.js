/* DOM helpers, formatting, and tiny dependency-free SVG charts. */

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else if (key === "html") node.innerHTML = value;
    else node.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function fmtTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function fmtDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString([], { month: "short", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

export function fmtMoney(amount, currency = "INR") {
  const n = Number(amount);
  if (!Number.isFinite(n)) return `${amount} ${currency}`;
  return `${currency} ${n.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function fmtNumber(n) {
  return Number(n ?? 0).toLocaleString();
}

export function short(id = "", keep = 12) {
  return id.length > keep + 2 ? id.slice(0, keep) + "…" : id;
}

export function decisionBadge(decision) {
  const kind = { allow: "allow", block: "block", escalate: "escalate" }[decision] || "neutral";
  return el("span", { class: `badge badge-${kind}` }, decision.toUpperCase());
}

export function riskBadge(score, band) {
  return el("span", { class: `badge badge-neutral badge-risk-${band}` }, `risk ${score} · ${band}`);
}

/* Sparkline: counts by bucket. values = [{t: epochMs, v: 1}] */
export function sparkline(events, { width = 560, height = 56, buckets = 30, color = "var(--accent)" } = {}) {
  if (!events.length) return null;
  const times = events.map((e) => e.t);
  const min = Math.min(...times), max = Math.max(...times);
  const span = Math.max(1, max - min);
  const counts = new Array(buckets).fill(0);
  for (const e of events) {
    const idx = Math.min(buckets - 1, Math.floor(((e.t - min) / span) * buckets));
    counts[idx] += e.v;
  }
  const peak = Math.max(1, ...counts);
  const bw = width / buckets;
  const parts = counts.map((c, i) => {
    const h = (c / peak) * (height - 6);
    return `<rect x="${(i * bw + 1).toFixed(1)}" y="${(height - h).toFixed(1)}" width="${Math.max(1, bw - 2).toFixed(1)}" height="${h.toFixed(1)}" rx="1.5" fill="${color}" opacity="${c ? 0.9 : 0.15}"/>`;
  });
  const svg = `<svg viewBox="0 0 ${width} ${height}" width="100%" height="${height}" role="img" aria-label="decision volume">${parts.join("")}</svg>`;
  const wrap = el("div");
  wrap.innerHTML = svg;
  return wrap.firstElementChild;
}

/* Horizontal per-family bars for AttackBench. rows = [{label, passed, total}] */
export function barRows(rows) {
  const wrap = el("div");
  for (const row of rows) {
    const pctVal = row.total ? Math.round((row.passed / row.total) * 100) : 0;
    const color = pctVal >= 95 ? "var(--allow)" : pctVal >= 80 ? "var(--escalate)" : "var(--block)";
    const bar = el("div", { style: "display:grid;grid-template-columns:220px 1fr 64px;gap:12px;align-items:center;padding:3px 0;" },
      el("span", { class: "mono", style: "font-size:12px;color:var(--text-2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" }, row.label),
      el("div", { style: "height:8px;background:var(--surface-2);border-radius:4px;overflow:hidden;" },
        el("div", { style: `height:100%;width:${pctVal}%;background:${color};border-radius:4px;transition:width var(--t-med) var(--ease);` })),
      el("span", { class: "mono", style: "font-size:12px;text-align:right;color:var(--text-2);" }, `${row.passed}/${row.total}`),
    );
    wrap.append(bar);
  }
  return wrap;
}

export function toast(message, kind = "ok") {
  const host = document.getElementById("toasts");
  const node = el("div", { class: `toast ${kind}` }, message);
  host.append(node);
  setTimeout(() => node.remove(), 4200);
}

export function emptyState(icon, title, text) {
  return el("div", { class: "empty" },
    el("div", { class: "empty-icon", "aria-hidden": "true" }, icon),
    el("h3", {}, title),
    el("p", {}, text),
  );
}

export function loading() {
  return el("div", { class: "loading" }, "loading …");
}
