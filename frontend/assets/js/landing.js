/* Landing behaviors: simulated decision-stream replay, scroll reveals,
   animated proof counters, copy buttons. All motion respects
   prefers-reduced-motion; the stream is clearly labeled SIMULATED. */

const REDUCED = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/* ------------------------------------------------------------------ */
/* Simulated decision stream (hero)                                    */
/* ------------------------------------------------------------------ */

const SCRIPT = [
  {
    decision: "allow", tool: "shopping_api.search_products",
    params: { query: "laptop" }, risk: [0, "low"], reasons: [],
  },
  {
    decision: "allow", tool: "web_browser.fetch_page",
    params: { uri: "vendor://lenovo-catalog/laptops" }, risk: [0, "low"], reasons: [],
  },
  {
    decision: "allow", tool: "web_browser.fetch_page",
    params: { uri: "https://deals-express.example/flash-sale" },
    risk: [10, "low"], reasons: [],
  },
  {
    decision: "block", tool: "shopping_api.purchase",
    params: { item: "laptop", brand: "Apple", unit_price: "15000", quantity: 500, currency: "INR", destination: "Mumbai" },
    risk: [65, "high"],
    reasons: ["AMOUNT_LIMIT_EXCEEDED", "QUANTITY_EXCEEDED", "BRAND_NOT_ALLOWED", "DESTINATION_NOT_ALLOWED", "EXTERNAL_INSTRUCTION_TAINT", "INTENT_DIVERGENCE"],
  },
];

function renderCard(step) {
  const card = document.createElement("div");
  card.className = `decision-card d-${step.decision}`;
  const head = document.createElement("div");
  head.className = "decision-head";
  const badge = document.createElement("span");
  badge.className = `badge badge-${step.decision}`;
  badge.textContent = step.decision.toUpperCase();
  const title = document.createElement("span");
  title.className = "decision-title";
  title.style.fontFamily = "var(--font-mono)";
  title.style.fontSize = "12.5px";
  title.textContent = step.tool;
  const risk = document.createElement("span");
  risk.className = "badge badge-neutral badge-risk-" + step.risk[1];
  risk.textContent = `risk ${step.risk[0]} · ${step.risk[1]}`;
  head.append(badge, title, risk);
  card.append(head);
  const params = document.createElement("div");
  params.className = "decision-params";
  params.textContent = JSON.stringify(step.params, null, 1);
  card.append(params);
  if (step.reasons.length) {
    const reasons = document.createElement("div");
    reasons.className = "reasons";
    for (const r of step.reasons) {
      const chip = document.createElement("span");
      chip.className = "reason";
      chip.textContent = r;
      reasons.append(chip);
    }
    card.append(reasons);
  }
  return card;
}

function runStream() {
  const host = document.getElementById("hero-stream");
  if (!host) return;
  host.replaceChildren();
  let i = 0;
  const stepDelay = REDUCED ? 400 : 1500;
  setInterval(() => {
    const step = SCRIPT[i % SCRIPT.length];
    host.append(renderCard(step));
    while (host.children.length > 3) host.firstChild.remove();
    i += 1;
  }, stepDelay);
}

/* ------------------------------------------------------------------ */
/* Scroll reveals + counters                                           */
/* ------------------------------------------------------------------ */

function setupReveals() {
  const targets = document.querySelectorAll(
    ".land-section > .land-split, .land-section > .land-h2, .land-section > .eyebrow, .proof-grid, .proof-caveat"
  );
  for (const node of targets) node.classList.add("reveal");
  if (REDUCED || !("IntersectionObserver" in window)) {
    for (const node of targets) node.classList.add("in");
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("in");
          observer.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.12 }
  );
  for (const node of targets) observer.observe(node);
}

function setupCounters() {
  const counters = document.querySelectorAll(".proof-num[data-count]");
  const animate = (node) => {
    const target = parseFloat(node.dataset.count);
    const suffix = node.dataset.suffix || "";
    if (REDUCED) {
      node.textContent = target + suffix;
      return;
    }
    const decimals = Number.isInteger(target) ? 0 : 1;
    const started = performance.now();
    const tick = (now) => {
      const p = Math.min(1, (now - started) / 900);
      const eased = 1 - Math.pow(1 - p, 3);
      node.textContent = (target * eased).toFixed(decimals) + suffix;
      if (p < 1) requestAnimationFrame(tick);
    };
    requestAnimationFrame(tick);
  };
  if (!("IntersectionObserver" in window)) {
    for (const node of counters) animate(node);
    return;
  }
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          animate(entry.target);
          observer.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.5 }
  );
  for (const node of counters) observer.observe(node);
}

/* ------------------------------------------------------------------ */
/* Copy buttons                                                        */
/* ------------------------------------------------------------------ */

function setupCopy() {
  for (const button of document.querySelectorAll(".copy-btn")) {
    button.addEventListener("click", async () => {
      const source = document.querySelector(button.dataset.copy);
      if (!source) return;
      try {
        await navigator.clipboard.writeText(source.textContent.trim());
        button.textContent = "copied ✓";
        setTimeout(() => { button.textContent = "copy"; }, 1600);
      } catch {
        button.textContent = "select & copy";
        setTimeout(() => { button.textContent = "copy"; }, 1600);
      }
    });
  }
}

/* ------------------------------------------------------------------ */

runStream();
setupReveals();
setupCounters();
setupCopy();
