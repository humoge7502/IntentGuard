/* App shell: hash router, navigation state, API-key modal, connection status. */
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
  host.replaceChildren(el("div", { class: "page-enter loading" }, "loading …"));
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

const importMeta = {
  onCleanup,
  setTitle,
  navigate,
  toast,
  refresh: renderRoute,
  refreshNavCounters,
};

/* ---------- API key modal ---------- */
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

  if (getKey()) {
    api.get("/api/v1/me")
      .then((me) => {
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
