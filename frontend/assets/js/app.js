/* App shell: hash router, navigation state, API-key modal, connection status,
   and the ⌘K command palette. */
import { api, getKey, setKey, openEventStream } from "./api.js";
import { el, toast } from "./helpers.js";
import { PAGES } from "./pages.js";

const outlet = () => document.getElementById("outlet");

let cleanupFns = [];
export function onCleanup(fn) { cleanupFns.push(fn); }
export function runCleanup() {
  for (const fn of cleanupFns) { try { fn(); } catch { /* noop */ } }
  cleanupFns = [];
}

export function setTitle(title, sub = "") {
  document.getElementById("page-title").textContent = title;
  document.getElementById("page-sub").textContent = sub;
}

export function navigate(hash) {
  location.hash = hash;
}

function currentRoute() {
  const raw = location.hash.replace(/^#\/?/, "");
  const [path] = raw.split("?");
  const parts = path.split("/").filter(Boolean);
  return { name: parts[0] || "overview", args: parts.slice(1) };
}

async function renderRoute() {
  runCleanup();
  const route = currentRoute();
  const page = PAGES[route.name] || PAGES.overview;
  document.querySelectorAll("[data-nav]").forEach((node) => {
    node.classList.toggle("active", node.dataset.nav === route.name);
  });
  const host = outlet();
  host.replaceChildren(skeletonPage());
  try {
    await page({ host, args: route.args, app: importMeta });
  } catch (err) {
    host.replaceChildren(
      el("div", { class: "error-box" }, err.message || String(err)),
      el("p", { style: "color:var(--text-3);font-size:13px;" },
        "If this is an auth problem, set your API key from the top-right button."),
    );
  }
  host.scrollIntoView({ block: "start" });
  document.getElementById("main").focus({ preventScroll: true });
}

function skeletonPage() {
  const bar = (w) => el("div", { class: "skeleton", style: `width:${w};height:14px;border-radius:6px;` });
  return el("div", { class: "page-enter", "aria-hidden": "true" },
    el("div", { class: "grid grid-4" }, ...Array.from({ length: 4 }, () =>
      el("div", { class: "card" }, bar("40%"), el("div", { style: "height:10px" }), bar("70%")))),
    el("div", { style: "height:16px" }),
    el("div", { class: "card" },
      ...Array.from({ length: 5 }, () =>
        el("div", { style: "display:flex;gap:12px;padding:10px 0;border-bottom:1px solid var(--border);" },
          bar("60px"), bar("30%"), bar("25%"), bar("60px")))));
}

const importMeta = {
  onCleanup,
  setTitle,
  navigate,
  toast,
  refresh: renderRoute,
  refreshNavCounters,
};

/* ------------------------------------------------------------------ */
/* Command palette (Ctrl/⌘ + K)                                        */
/* ------------------------------------------------------------------ */

const COMMANDS = [
  { label: "Overview", hint: "page", run: () => { location.hash = "#/overview"; } },
  { label: "Action Firewall — live stream", hint: "page", run: () => { location.hash = "#/firewall"; } },
  { label: "Approvals", hint: "page", run: () => { location.hash = "#/approvals"; } },
  { label: "Intents", hint: "page", run: () => { location.hash = "#/intents"; } },
  { label: "Policies", hint: "page", run: () => { location.hash = "#/policies"; } },
  { label: "Capabilities", hint: "page", run: () => { location.hash = "#/capabilities"; } },
  { label: "Trajectories", hint: "page", run: () => { location.hash = "#/sessions"; } },
  { label: "AttackBench", hint: "page", run: () => { location.hash = "#/attackbench"; } },
  { label: "Audit", hint: "page", run: () => { location.hash = "#/audit"; } },
  { label: "Settings", hint: "page", run: () => { location.hash = "#/settings"; } },
  {
    label: "Run demo — intent divergence attack", hint: "action", admin: true,
    run: async () => {
      toast("Running intent-divergence demo…");
      try {
        const t = await api.post("/api/v1/demo/intent_divergence/run");
        toast(`Demo complete — outcome: ${t.outcome.toUpperCase()}`, "ok");
        location.hash = "#/demo";
      } catch (err) { toast(err.message, "err"); }
    },
  },
  {
    label: "Run demo — credential-harvest trajectory", hint: "action", admin: true,
    run: async () => {
      toast("Running trajectory demo…");
      try {
        const t = await api.post("/api/v1/demo/trajectory_credential_harvest/run");
        toast(`Demo complete — outcome: ${t.outcome.toUpperCase()}`, "ok");
        location.hash = "#/demo";
      } catch (err) { toast(err.message, "err"); }
    },
  },
  {
    label: "Verify audit chain integrity", hint: "action", admin: true,
    run: async () => {
      try {
        const verdict = await api.post("/api/v1/audit/verify");
        toast(verdict.valid ? `Chain valid — ${verdict.events} events` : `CHAIN BROKEN at seq ${verdict.broken_at_seq}`, verdict.valid ? "ok" : "err");
        location.hash = "#/audit";
      } catch (err) { toast(err.message, "err"); }
    },
  },
  { label: "Public landing page", hint: "open", run: () => { window.location.href = "/"; } },
];

let paletteState = { open: false, index: 0, filtered: COMMANDS };

function openPalette() {
  const overlay = document.getElementById("palette");
  overlay.hidden = false;
  paletteState = { open: true, index: 0, filtered: COMMANDS };
  const input = overlay.querySelector("#palette-input");
  input.value = "";
  renderPaletteList("");
  input.focus();
}

function closePalette() {
  const overlay = document.getElementById("palette");
  overlay.hidden = true;
  paletteState.open = false;
}

function renderPaletteList(query) {
  const q = query.trim().toLowerCase();
  const me = sessionStorage.getItem("ig_role");
  paletteState.filtered = COMMANDS.filter((c) =>
    (!c.admin || me === "admin") && c.label.toLowerCase().includes(q));
  const list = document.getElementById("palette-list");
  paletteState.index = Math.min(paletteState.index, Math.max(0, paletteState.filtered.length - 1));
  list.replaceChildren(...paletteState.filtered.map((cmd, i) =>
    el("div", {
      class: `palette-item ${i === paletteState.index ? "active" : ""}`,
      role: "option",
      "aria-selected": i === paletteState.index ? "true" : "false",
      onclick: () => executeCommand(cmd),
      onmousemove: () => {
        paletteState.index = i;
        list.querySelectorAll(".palette-item").forEach((n, j) => {
          n.classList.toggle("active", j === i);
          n.setAttribute("aria-selected", j === i ? "true" : "false");
        });
      },
    },
      el("span", {}, cmd.label),
      el("span", { class: "mono-eyebrow" }, cmd.hint))));
  if (!paletteState.filtered.length) {
    list.replaceChildren(el("div", { class: "palette-item", style: "color:var(--text-3);" }, "No matching commands"));
  }
}

async function executeCommand(cmd) {
  closePalette();
  await cmd.run();
}

function setupPalette() {
  const overlay = document.getElementById("palette");
  if (!overlay) return;
  const input = overlay.querySelector("#palette-input");
  window.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      paletteState.open ? closePalette() : openPalette();
    } else if (event.key === "Escape" && paletteState.open) {
      closePalette();
    }
  });
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) closePalette();
  });
  input.addEventListener("input", () => {
    paletteState.index = 0;
    renderPaletteList(input.value);
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      paletteState.index = Math.min(paletteState.index + 1, paletteState.filtered.length - 1);
      renderPaletteList(input.value);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      paletteState.index = Math.max(paletteState.index - 1, 0);
      renderPaletteList(input.value);
    } else if (event.key === "Enter") {
      event.preventDefault();
      const cmd = paletteState.filtered[paletteState.index];
      if (cmd) executeCommand(cmd);
    }
  });
  const trigger = document.getElementById("palette-btn");
  if (trigger) trigger.addEventListener("click", openPalette);
}

/* ------------------------------------------------------------------ */
/* API key modal + boot                                                */
/* ------------------------------------------------------------------ */

function openKeyModal() {
  const modal = document.getElementById("key-modal");
  const error = document.getElementById("key-error");
  const input = document.getElementById("key-input");
  error.hidden = true;
  input.value = getKey();
  modal.hidden = false;
  input.focus();
}

function closeKeyModal() {
  document.getElementById("key-modal").hidden = true;
}

async function submitKey(event) {
  event.preventDefault();
  const input = document.getElementById("key-input");
  const error = document.getElementById("key-error");
  const candidate = input.value.trim();
  if (!candidate) {
    error.textContent = "Enter an API key.";
    error.hidden = false;
    return;
  }
  setKey(candidate);
  try {
    const me = await api.get("/api/v1/me");
    sessionStorage.setItem("ig_role", me.role);
    closeKeyModal();
    toast(`Connected as ${me.role} in org ${me.org_id.slice(0, 10)}…`);
    setConnection("ok", `org ${me.org_id.slice(0, 8)}… · ${me.role}`);
    refreshNavCounters();
    renderRoute();
  } catch (err) {
    setKey("");
    error.textContent = err.message;
    error.hidden = false;
  }
}

function setConnection(kind, text) {
  const host = document.getElementById("conn-status");
  host.className = `conn ${kind}`;
  document.getElementById("conn-text").textContent = text;
}

export async function refreshNavCounters() {
  if (!getKey()) return;
  try {
    const approvals = await api.get("/api/v1/approvals?status=pending");
    const pending = approvals.approvals.length;
    const badge = document.getElementById("nav-approvals");
    badge.hidden = pending === 0;
    badge.textContent = String(pending);
  } catch { /* nav counters are best-effort */ }
}

/* ---------- boot ---------- */
function boot() {
  document.getElementById("key-btn").addEventListener("click", openKeyModal);
  document.getElementById("key-form").addEventListener("submit", submitKey);
  document.getElementById("key-modal").addEventListener("click", (event) => {
    if (event.target === event.currentTarget) closeKeyModal();
  });
  window.addEventListener("hashchange", renderRoute);
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeKeyModal();
  });
  setupPalette();

  if (getKey()) {
    api.get("/api/v1/me")
      .then((me) => {
        sessionStorage.setItem("ig_role", me.role);
        setConnection("ok", `org ${me.org_id.slice(0, 8)}… · ${me.role}`);
        refreshNavCounters();
      })
      .catch(() => {
        setConnection("err", "api key invalid");
        openKeyModal();
      });
  } else {
    openKeyModal();
  }

  renderRoute();
}

boot();
