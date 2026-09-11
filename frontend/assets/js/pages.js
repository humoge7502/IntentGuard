/* Control-plane pages. Each page: async render({host, args, app}). */
import { api, openEventStream, getKey } from "./api.js";
import {
  el, fmtTime, fmtDateTime, fmtMoney, fmtNumber, short,
  decisionBadge, riskBadge, sparkline, barRows, toast, emptyState, loading,
} from "./helpers.js";

/* ------------------------------------------------------------------ */
/* shared renderers                                                     */
/* ------------------------------------------------------------------ */

function decisionCard(decision, { showParams = true } = {}) {
  const proposal = decision.versions?.proposal || {};
  const reasons = decision.reasons || [];
  return el("div", { class: `decision-card d-${decision.decision}` },
    el("div", { class: "decision-head" },
      decisionBadge(decision.decision),
      el("span", { class: "decision-title mono" },
        `${proposal.tool || "?"}.${proposal.operation || "?"}`),
      riskBadge(decision.risk?.score ?? 0, decision.risk?.band ?? "low"),
      el("span", { class: "when" }, fmtTime(decision.created_at)),
    ),
    showParams && el("div", { class: "decision-params" },
      JSON.stringify(proposal.params ?? {}, null, 1)),
    reasons.length > 0 && el("div", { class: "reasons" },
      reasons.map((r) => el("span", {
        class: `reason ${/TAINT|DIVERGENCE|HARVEST|REPLAY|CRITICAL/.test(r) ? "" : "info"}`,
      }, r))),
  );
}

function intentChips(intent) {
  return el("div", {},
    (intent.constraints || []).map((c) => {
      let label = c.kind;
      if (c.kind === "amount_limit") label = `budget ≤ ${fmtMoney(c.max_amount, c.currency)}`;
      else if (c.kind === "brand_allow") label = `brands: ${c.allowed.join(", ")}`;
      else if (c.kind === "destination_allow") label = `destinations: ${c.allowed.join(", ")}`;
      else if (c.kind === "quantity_max") label = `qty ≤ ${c.max_quantity}${c.item ? " " + c.item : ""}`;
      else if (c.kind === "approval_required") label = `approval: ${c.operations.join(", ")}`;
      else if (c.kind === "time_window") label = `window until ${fmtDateTime(c.not_after)}`;
      return el("span", { class: "chip" }, label);
    }),
  );
}

function intentGraphTree(graph) {
  const build = (nodes, edges, parentId) => {
    const children = edges.filter((e) => e.from === parentId).map((e) => nodes.find((n) => n.id === e.to));
    if (!children.length) return null;
    return el("ul", {}, children.map((node) =>
      el("li", { class: `tree-node k-${node.type}` },
        el("span", { class: "tree-kind" }, node.type),
        el("span", { class: "tree-label" }, node.label),
        node.detail ? el("span", { class: "tree-detail" }, ` — ${node.detail}`) : null,
        build(nodes, edges, node.id)),
    ));
  };
  const root = graph.nodes.find((n) => !graph.edges.some((e) => e.to === n.id));
  return el("div", { class: "tree" },
    el("div", { class: "tree-node k-goal" },
      el("span", { class: "tree-kind" }, "goal"),
      el("span", { class: "tree-label" }, root?.label ?? "")),
    build(graph.nodes, graph.edges, root?.id));
}

/* ------------------------------------------------------------------ */
/* Overview                                                             */
/* ------------------------------------------------------------------ */

async function overview({ host, app }) {
  app.setTitle("Overview", "Live state of agent authorization across this organization");
  const [metrics, decisions] = await Promise.all([
    api.get("/api/v1/metrics/summary"),
    api.get("/api/v1/decisions?limit=200"),
  ]);

  const events = decisions.decisions.map((d) => ({ t: new Date(d.created_at).getTime(), v: 1 }));
  const chart = sparkline(events);

  const metric = (label, value, note, tone = "") =>
    el("div", { class: `card metric tone-${tone}` },
      el("div", { class: "metric-label" }, label),
      el("div", { class: "metric-value" }, fmtNumber(value)),
      note ? el("div", { class: "metric-note" }, note) : null);

  host.replaceChildren(
    el("div", { class: "page-enter" },
      el("div", { class: "grid grid-4 section" },
        metric("Actions evaluated", metrics.decisions, "all firewall decisions"),
        metric("Allowed", metrics.allowed, "executed within intent", "allow"),
        metric("Blocked", metrics.blocked, "hard violations", "block"),
        metric("Escalated", metrics.escalated, "awaiting human decision", "escalate"),
      ),
      el("div", { class: "grid grid-4 section" },
        metric("Agents", metrics.agents, "registered identities", "accent"),
        metric("Intents", metrics.intents, "compiled human goals", "accent"),
        metric("Sessions", metrics.sessions, "bounded agent runs", "accent"),
        metric("Capabilities", metrics.capabilities, "least-privilege grants", "accent"),
      ),
      el("div", { class: "section" },
        el("p", { class: "eyebrow" }, "Decision volume (recent)"),
        el("div", { class: "card" }, chart || emptyState("◌", "No decisions yet", "Run a demo or send actions through the firewall.")),
      ),
      el("div", { class: "section" },
        el("p", { class: "eyebrow" }, "Recent decisions"),
        recentDecisionTable(decisions.decisions.slice(0, 12)),
      ),
    ),
  );
  app.refreshNavCounters();
}

function recentDecisionTable(decisions) {
  if (!decisions.length) return emptyState("◈", "Nothing evaluated yet", "Firewall decisions will appear here.");
  return el("div", { class: "table-wrap" },
    el("table", { class: "data" },
      el("thead", {}, el("tr", {},
        el("th", {}, "Decision"), el("th", {}, "Tool · Operation"),
        el("th", {}, "Reasons"), el("th", { class: "num" }, "Risk"), el("th", {}, "When"))),
      el("tbody", {}, decisions.map((d) => {
        const proposal = d.versions?.proposal || {};
        return el("tr", { class: "rowlink", onclick: () => { location.hash = `#/sessions/${d.session_id}`; } },
          el("td", {}, decisionBadge(d.decision)),
          el("td", { class: "mono" }, `${proposal.tool || "?"}.${proposal.operation || "?"}`),
          el("td", {}, (d.reasons || []).join(", ") || "—"),
          el("td", { class: "num" }, String(d.risk?.score ?? 0)),
          el("td", { class: "mono" }, fmtTime(d.created_at)));
      }))));
}

/* ------------------------------------------------------------------ */
/* Live firewall stream                                                 */
/* ------------------------------------------------------------------ */

async function firewall({ host, app }) {
  app.setTitle("Action Firewall", "Every proposed action, decided before execution");
  const status = el("span", { class: "stream-status" }, "connecting…");
  const filter = el("select", { class: "select", style: "width:180px", "aria-label": "Filter decisions" },
    el("option", { value: "all" }, "All decisions"),
    el("option", { value: "block" }, "Blocks only"),
    el("option", { value: "escalate" }, "Escalations only"),
    el("option", { value: "allow" }, "Allowed only"));
  const stream = el("div", {});
  let current = "all";

  const paint = (decision) => {
    if (current !== "all" && decision.decision !== current) return;
    stream.prepend(decisionCard(decision));
    while (stream.children.length > 80) stream.lastChild.remove();
  };

  const close = openEventStream(
    (event) => {
      if (event.type === "decision") paint(event.decision);
      if (event.type === "approval") toast("New approval request", "ok");
    },
    (state) => {
      status.textContent = state === "live" ? "● live stream connected" : "○ stream disconnected — reconnecting…";
      status.className = `stream-status ${state === "live" ? "live" : ""}`;
      document.getElementById("nav-live").hidden = state !== "live";
    },
  );
  document.getElementById("conn-status").className = "conn ok";
  app.onCleanup(() => {
    close();
    document.getElementById("nav-live").hidden = true;
  });

  const history = await api.get("/api/v1/decisions?limit=30");
  filter.addEventListener("change", () => {
    current = filter.value;
    stream.replaceChildren();
    history.decisions
      .filter((d) => current === "all" || d.decision === current)
      .forEach(paint);
  });
  history.decisions.slice().reverse().forEach(paint);

  host.replaceChildren(
    el("div", { class: "page-enter" },
      el("div", { class: "stream-toolbar" },
        status, el("span", { style: "flex:1" }), filter),
      el("p", { class: "eyebrow" }, "Decisions — newest first"),
      stream.childElementCount || history.decisions.length
        ? stream
        : emptyState("⚡", "Stream is live, waiting for actions",
          "Send an action through POST /api/v1/firewall/evaluate or run a demo.")),
  );
}

/* ------------------------------------------------------------------ */
/* Intents                                                              */
/* ------------------------------------------------------------------ */

async function intents({ host, args, app }) {
  if (args.length) return intentDetail({ host, args, app });
  app.setTitle("Intents", "Human goals compiled into verifiable structure");
  const data = await api.get("/api/v1/intents");
  if (!data.intents.length) {
    host.replaceChildren(el("div", { class: "page-enter" },
      emptyState("◎", "No intents yet",
        "Compile one via POST /api/v1/intents with plain-language text.")));
    return;
  }
  host.replaceChildren(el("div", { class: "page-enter" },
    el("div", { class: "table-wrap" },
      el("table", { class: "data" },
        el("thead", {}, el("tr", {},
          el("th", {}, "Goal"), el("th", {}, "Operations"), el("th", {}, "Constraints"),
          el("th", { class: "num" }, "Ambiguities"), el("th", {}, "Compiled"))),
        el("tbody", {}, data.intents.map((intent) =>
          el("tr", { class: "rowlink", onclick: () => { location.hash = `#/intents/${intent.intent_id}`; } },
            el("td", {}, el("strong", {}, intent.goal),
              el("div", { class: "tree-detail" }, short(intent.raw_text, 72))),
            el("td", { class: "mono" }, intent.allowed_operations.join(", ")),
            el("td", {}, String(intent.constraints.length)),
            el("td", { class: "num" }, String(intent.ambiguities.length)),
            el("td", { class: "mono" }, intent.compiled_by))))))));
}

async function intentDetail({ host, args, app }) {
  const [intentId] = args;
  const [intent, graph] = await Promise.all([
    api.get(`/api/v1/intents/${intentId}`),
    api.get(`/api/v1/intents/${intentId}/graph`),
  ]);
  app.setTitle(`Intent · ${intent.goal}`, "Why actions are or are not authorized by this intent");
  host.replaceChildren(el("div", { class: "page-enter" },
    el("div", { class: "grid grid-2" },
      el("div", { class: "card" },
        el("h3", { class: "card-title" }, "Original words"),
        el("p", { style: "color:var(--text-2);font-size:14px;" }, `“${intent.raw_text}”`),
        el("dl", { class: "kv", style: "margin-top:12px;" },
          el("dt", {}, "Intent ID"), el("dd", {}, intent.intent_id),
          el("dt", {}, "Version"), el("dd", {}, `v${intent.version}`),
          el("dt", {}, "Compiled by"), el("dd", {}, intent.compiled_by),
          el("dt", {}, "Created"), el("dd", {}, fmtDateTime(intent.created_at))),
        el("p", { class: "eyebrow", style: "margin-top:16px;" }, "Authorized operations"),
        el("div", {}, intent.allowed_operations.map((op) => el("span", { class: "chip" }, op))),
        el("p", { class: "eyebrow", style: "margin-top:16px;" }, "Constraints"),
        intentChips(intent)),
      el("div", { class: "card" },
        el("h3", { class: "card-title" }, "Intent graph"),
        intentGraphTree(graph)),
    ),
    intent.ambiguities.length > 0 && el("div", { class: "card", style: "margin-top:12px;" },
      el("h3", { class: "card-title" }, "Ambiguities recorded at compile time"),
      el("ul", { style: "margin:0;padding-left:18px;color:var(--text-2);font-size:13px;" },
        intent.ambiguities.map((a) => el("li", {},
          el("strong", { style: "color:var(--escalate);text-transform:uppercase;font-size:11px;" }, `${a.severity} `),
          a.message)))),
  ));
}

/* ------------------------------------------------------------------ */
/* Policies                                                             */
/* ------------------------------------------------------------------ */

async function policies({ host, app }) {
  app.setTitle("Policies", "Narrowing-only rules: denies block, limits cap — nothing widens");
  const [data, me] = await Promise.all([api.get("/api/v1/policies"), api.get("/api/v1/me")]);
  const isAdmin = me.role === "admin";

  const form = el("form", { class: "card", style: isAdmin ? "" : "display:none" },
    el("h3", { class: "card-title" }, "New policy rule"),
    el("div", { class: "form-row" },
      selectField("Layer", "layer", ["organization", "user", "agent", "intent"]),
      selectField("Effect", "effect", ["deny", "limit"]),
      inputField("Name", "name", "quarterly-cap"),
      inputField("Tool (* = any)", "tool", "*"),
      inputField("Operation (* = any)", "operation", "purchase"),
      inputField("Max amount (limit)", "max_amount", "500000")),
    el("div", { class: "form-row", style: "margin-top:8px;" },
      inputField("Currency", "currency", "INR"),
      inputField("Reason code", "reason_code", "POLICY_LIMIT"),
      el("button", { class: "btn btn-primary", type: "submit" }, "Add rule")),
    el("p", { class: "metric-note", style: "margin-top:8px;" },
      "Deny rules block matching actions. Limit rules cap financial exposure; the strictest matching layer wins."));

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const fd = new FormData(form);
    try {
      await api.post("/api/v1/policies", {
        layer: fd.get("layer"), effect: fd.get("effect"), name: fd.get("name"),
        tool: fd.get("tool") || null, operation: fd.get("operation") || null,
        max_amount: fd.get("max_amount") || null, currency: fd.get("currency") || "INR",
        reason_code: fd.get("reason_code") || "POLICY_DENY",
      });
      toast("Policy rule added");
      app.refresh();
    } catch (err) { toast(err.message, "err"); }
  });

  host.replaceChildren(el("div", { class: "page-enter" },
    form,
    el("p", { class: "eyebrow", style: "margin-top:20px;" }, "Active rules"),
    data.rules.length
      ? el("div", { class: "table-wrap" },
          el("table", { class: "data" },
            el("thead", {}, el("tr", {},
              el("th", {}, "Layer"), el("th", {}, "Name"), el("th", {}, "Effect"),
              el("th", {}, "Scope"), el("th", { class: "num" }, "Cap"), el("th", {}, "Reason code"))),
            el("tbody", {}, data.rules.map((rule) =>
              el("tr", {},
                el("td", {}, el("span", { class: "badge badge-accent" }, rule.layer)),
                el("td", {}, rule.name),
                el("td", {}, el("span", {
                  class: `badge ${rule.effect === "deny" ? "badge-block" : "badge-escalate"}`,
                }, rule.effect)),
                el("td", { class: "mono" }, `${rule.tool || "*"} / ${rule.operation || "*"}`),
                el("td", { class: "num" }, rule.max_amount ? fmtMoney(rule.max_amount, rule.currency) : "—"),
                el("td", { class: "mono" }, rule.reason_code))))))
      : emptyState("≡", "No policy rules", "The capability alone bounds the agent until rules are added."),
  ));
}

function inputField(label, name, placeholder = "") {
  const id = `field-${name}`;
  return el("div", {},
    el("label", { class: "field-label", for: id }, label),
    el("input", { class: "input", name, id, placeholder }));
}

function selectField(label, name, options) {
  const id = `field-${name}`;
  return el("div", {},
    el("label", { class: "field-label", for: id }, label),
    el("select", { class: "select", name, id },
      options.map((opt) => el("option", { value: opt }, opt))));
}

/* ------------------------------------------------------------------ */
/* Capabilities                                                         */
/* ------------------------------------------------------------------ */

async function capabilities({ host, args, app }) {
  app.setTitle("Capabilities", "Least-privilege grants derived from intent ∩ policy");
  const data = await api.get("/api/v1/capabilities");
  if (!data.capabilities.length) {
    host.replaceChildren(el("div", { class: "page-enter" },
      emptyState("⬡", "No capabilities minted", "Starting a session mints a capability automatically.")));
    return;
  }
  host.replaceChildren(el("div", { class: "page-enter" },
    data.capabilities.map((cap) => el("div", { class: "card" },
      el("div", { class: "decision-head" },
        el("span", { class: "decision-title mono" }, cap.capability_id),
        el("span", {
          class: `badge ${cap.status === "active" ? "badge-allow" : "badge-block"}`,
        }, cap.status),
        el("span", { class: "badge badge-neutral" }, `v${cap.version}`),
        cap.budget ? el("span", { class: "badge badge-accent" },
          `budget ≤ ${fmtMoney(cap.budget.max_amount, cap.budget.currency)}`) : null,
        cap.expires_at ? el("span", { class: "badge badge-neutral" }, `expires ${fmtDateTime(cap.expires_at)}`) : null,
      ),
      el("div", { style: "margin-top:10px;" },
        cap.scopes.map((scope) => el("div", { style: "margin-bottom:6px;" },
          el("span", { class: "chip" }, el("strong", {}, scope.tool)),
          scope.operations.map((op) => el("span", { class: "chip" }, op)),
          scope.param_constraints.length
            ? el("span", { class: "tree-detail" }, ` · constrained: ${scope.param_constraints.length}`)
            : null))),
      cap.revoked_reason ? el("p", { class: "metric-note" }, `revoked: ${cap.revoked_reason}`) : null,
    ))));
}

/* ------------------------------------------------------------------ */
/* Trajectories (sessions)                                              */
/* ------------------------------------------------------------------ */

async function sessions({ host, args, app }) {
  if (args.length) return sessionDetail({ host, args, app });
  app.setTitle("Trajectories", "Agent execution histories with per-step verdicts");
  const [sessionsData, decisions] = await Promise.all([
    api.get("/api/v1/metrics/summary"), api.get("/api/v1/decisions?limit=200"),
  ]);
  // group decisions by session for the list view
  const bySession = new Map();
  for (const d of decisions.decisions) {
    if (!bySession.has(d.session_id)) bySession.set(d.session_id, { blocked: 0, total: 0, last: d });
    const entry = bySession.get(d.session_id);
    entry.total += 1;
    if (d.decision === "block") entry.blocked += 1;
  }
  if (!bySession.size) {
    host.replaceChildren(el("div", { class: "page-enter" },
      emptyState("⌁", "No sessions yet", "Start a session and evaluate actions to build trajectories.")));
    return;
  }
  host.replaceChildren(el("div", { class: "page-enter" },
    el("div", { class: "table-wrap" },
      el("table", { class: "data" },
        el("thead", {}, el("tr", {},
          el("th", {}, "Session"), el("th", {}, "Agent"), el("th", { class: "num" }, "Decisions"),
          el("th", { class: "num" }, "Blocked"), el("th", {}, "Last activity"))),
        el("tbody", {}, [...bySession.entries()].map(([sessionId, entry]) =>
          el("tr", { class: "rowlink", onclick: () => { location.hash = `#/sessions/${sessionId}`; } },
            el("td", { class: "mono" }, short(sessionId, 16)),
            el("td", { class: "mono" }, short(entry.last.agent_id, 16)),
            el("td", { class: "num" }, String(entry.total)),
            el("td", { class: "num", style: entry.blocked ? "color:var(--block)" : "" }, String(entry.blocked)),
            el("td", { class: "mono" }, fmtTime(entry.last.created_at)))))))));
}

async function sessionDetail({ host, args, app }) {
  const [sessionId] = args;
  const view = await api.get(`/api/v1/sessions/${sessionId}`);
  app.setTitle(`Trajectory · ${short(sessionId, 14)}`, "Replayable sequence of proposals → decisions");
  const session = view.session;
  const intent = view.intent;

  const timeline = el("div", { class: "timeline" });
  const steps = view.decisions.slice().reverse();
  for (const decision of steps) {
    const proposal = decision.versions?.proposal || {};
    timeline.append(el("div", {
      class: `tl-step ${decision.decision === "allow" ? "ok" : decision.decision === "escalate" ? "warn" : "bad"}`,
    },
      el("span", { class: "tl-dot", "aria-hidden": "true" },
        decision.decision === "allow" ? "✓" : decision.decision === "escalate" ? "!" : "✗"),
      el("div", { class: "decision-head" },
        el("span", { class: "tl-title mono" }, `${proposal.tool}.${proposal.operation}`),
        decisionBadge(decision.decision),
        riskBadge(decision.risk?.score ?? 0, decision.risk?.band ?? "low"),
        el("span", { class: "when mono", style: "color:var(--text-3);font-size:11px;margin-left:auto;" },
          `${fmtTime(decision.created_at)} · ${decision.latency_ms}ms`)),
      (decision.reasons || []).length
        ? el("div", { class: "reasons" }, decision.reasons.map((r) => el("span", { class: "reason info" }, r)))
        : null,
      el("div", { class: "decision-params" }, JSON.stringify(proposal.params ?? {}, null, 1)),
    ));
  }

  host.replaceChildren(el("div", { class: "page-enter" },
    el("div", { class: "grid grid-2" },
      el("div", { class: "card" },
        el("h3", { class: "card-title" }, "Session"),
        el("dl", { class: "kv" },
          el("dt", {}, "Session"), el("dd", {}, session.session_id),
          el("dt", {}, "Agent"), el("dd", {}, session.agent_id),
          el("dt", {}, "Intent"), el("dd", {}, `${intent ? intent.goal : "?"} (${short(session.intent_id, 12)})`),
          el("dt", {}, "Capability"), el("dd", {}, short(session.capability_id, 16)),
          el("dt", {}, "Degraded"), el("dd", {}, session.degraded ? "YES — high-impact actions need approval" : "no"),
          el("dt", {}, "Started"), el("dd", {}, fmtDateTime(session.created_at))),
        intent ? el("div", { style: "margin-top:12px;" },
          el("p", { class: "eyebrow" }, "Intent constraints"),
          intentChips(intent)) : null),
      el("div", { class: "card" },
        el("h3", { class: "card-title" }, "Checks of latest decision"),
        latestChecksTable(view.decisions[0]))),
    el("div", { class: "card", style: "margin-top:12px;" },
      el("h3", { class: "card-title" }, "Trajectory"),
      steps.length ? timeline : emptyState("⌁", "No actions yet", "Proposals appear here as timeline steps.")),
  ));
}

function latestChecksTable(decision) {
  if (!decision) return emptyState("◌", "No decisions", "—");
  return el("table", { class: "data" },
    el("thead", {}, el("tr", {}, el("th", {}, "Check"), el("th", {}, "Status"), el("th", {}, "Detail"))),
    el("tbody", {}, (decision.checks || []).map((check) =>
      el("tr", {},
        el("td", { class: "mono" }, check.check),
        el("td", {}, el("span", {
          class: `badge ${check.status === "pass" ? "badge-allow" : check.status === "fail" ? "badge-block" : "badge-escalate"}`,
        }, check.status)),
        el("td", { style: "color:var(--text-2);font-size:12px;" }, check.detail)))));
}

/* ------------------------------------------------------------------ */
/* Approvals                                                            */
/* ------------------------------------------------------------------ */

async function approvals({ host, app }) {
  app.setTitle("Approvals", "Human authorization bound to one exact action digest");
  const me = await api.get("/api/v1/me");
  const data = await api.get("/api/v1/approvals");
  const isAdmin = me.role === "admin";

  const act = async (approvalId, action) => {
    const approver = prompt("Your name / ID (recorded in the audit chain):");
    if (!approver) return;
    try {
      await api.post(`/api/v1/approvals/${approvalId}/${action}`, { approver });
      toast(`Approval ${action}ed`);
      app.refresh();
    } catch (err) { toast(err.message, "err"); }
  };

  host.replaceChildren(el("div", { class: "page-enter" },
    data.approvals.length
      ? data.approvals.map((approval) => el("div", { class: `decision-card d-${approval.status === "pending" ? "escalate" : approval.status === "granted" ? "allow" : "block"}` },
          el("div", { class: "decision-head" },
            el("span", {
              class: `badge ${approval.status === "pending" ? "badge-escalate" : approval.status === "granted" ? "badge-allow" : "badge-block"}`,
            }, approval.status),
            el("span", { class: "decision-title mono" },
              `${approval.action_summary.tool}.${approval.action_summary.operation}`),
            el("span", { class: "when" }, fmtDateTime(approval.requested_at))),
          el("div", { class: "decision-params" }, JSON.stringify(approval.action_summary.params ?? {}, null, 1)),
          el("div", { class: "reasons" }, (approval.reasons || []).map((r) => el("span", { class: "reason warn" }, r))),
          el("div", { class: "authorized-vs" },
            el("span", {}, "digest: ", el("b", {}, short(approval.action_digest, 18))),
            el("span", {}, "expires: ", el("b", {}, fmtDateTime(approval.expires_at))),
            approval.granted_by ? el("span", {}, "by: ", el("b", {}, approval.granted_by)) : null),
          approval.status === "pending" && isAdmin
            ? el("div", { class: "modal-actions", style: "justify-content:flex-start;margin-top:10px;" },
                el("button", { class: "btn btn-success btn-sm", onclick: () => act(approval.approval_id, "grant") }, "Grant"),
                el("button", { class: "btn btn-danger btn-sm", onclick: () => act(approval.approval_id, "deny") }, "Deny"),
                el("span", { class: "metric-note", style: "align-self:center;" },
                  "Grant applies to this exact action only — single use."))
            : null))
      : emptyState("⏸", "No approval requests", "Escalations create requests bound to one action digest each."),
  ));
  app.refreshNavCounters();
}

/* ------------------------------------------------------------------ */
/* Audit                                                                */
/* ------------------------------------------------------------------ */

async function audit({ host, args, app }) {
  app.setTitle("Audit", "Hash-chained, tamper-evident record of every decision and lifecycle event");
  const me = await api.get("/api/v1/me");
  const data = await api.get("/api/v1/audit?limit=300");

  const verdictBox = el("div", { id: "audit-verdict" });
  async function verify() {
    try {
      const verdict = await api.post("/api/v1/audit/verify");
      verdictBox.replaceChildren(el("div", { class: "error-box", style: verdict.valid ? "background:var(--allow-dim);border-color:rgba(62,207,142,.3);color:var(--allow);" : "" },
        verdict.valid
          ? `✓ chain valid — ${verdict.events} events, no tampering detected`
          : `✗ chain BROKEN at seq ${verdict.broken_at_seq}`));
    } catch (err) {
      toast(err.message, "err");
    }
  }
  if (me.role === "admin") verify();
  else verdictBox.append(el("p", { class: "metric-note" }, "Chain verification requires an admin key."));

  host.replaceChildren(el("div", { class: "page-enter" },
    el("div", { class: "card" },
      el("h3", { class: "card-title" }, "Chain integrity"),
      el("div", { class: "form-row" }, verdictBox,
        me.role === "admin" ? el("button", { class: "btn btn-sm", onclick: verify, type: "button" }, "Re-verify") : null),
      el("p", { class: "metric-note" },
        "Tamper-evident: edits or deletions break the chain. Not immutable against an attacker who can rewrite the whole store — see SECURITY_MODEL.md.")),
    el("div", { class: "table-wrap", style: "margin-top:12px;" },
      el("table", { class: "data" },
        el("thead", {}, el("tr", {},
          el("th", { class: "num" }, "Seq"), el("th", {}, "Type"), el("th", {}, "Detail"), el("th", {}, "Hash"), el("th", {}, "When"))),
        el("tbody", {}, data.events.slice().reverse().map((event) =>
          el("tr", {},
            el("td", { class: "num" }, String(event.seq)),
            el("td", { class: "mono" }, event.event_type),
            el("td", { class: "tree-detail", style: "max-width:420px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" },
              JSON.stringify(event.payload)),
            el("td", { class: "mono", style: "color:var(--text-3);" }, short(event.hash, 12)),
            el("td", { class: "mono" }, fmtTime(event.created_at))))))),
  ));
}

/* ------------------------------------------------------------------ */
/* AttackBench                                                          */
/* ------------------------------------------------------------------ */

async function attackbench({ host, app }) {
  app.setTitle("AttackBench", "Adversarial evaluation against the live firewall — all sandboxed");
  const me = await api.get("/api/v1/me");
  const resultBox = el("div", {},
    el("div", { class: "empty" },
      el("div", { class: "empty-icon" }, "⊘"),
      el("h3", {}, "No run in this tab yet"),
      el("p", {}, "Run the benchmark to evaluate every attack family against this deployment.")));

  async function run() {
    const max = Number(document.getElementById("bench-size").value) || 40;
    resultBox.replaceChildren(el("div", { class: "loading" }, `running AttackBench (≤ ${max}/family) …`));
    try {
      const report = await api.post("/api/v1/benchmarks/run", { max_per_family: max });
      resultBox.replaceChildren(benchReport(report));
    } catch (err) {
      resultBox.replaceChildren(el("div", { class: "error-box" }, err.message));
    }
  }

  const toolbar = el("div", { class: "card" },
    el("div", { class: "form-row" },
      el("div", {},
        el("label", { class: "field-label", for: "bench-size" }, "Scenarios per family (max)"),
        el("input", { class: "input", id: "bench-size", type: "number", value: "40", min: "1", max: "500" })),
      el("button", { class: "btn btn-primary", onclick: run, type: "button",
        disabled: me.role !== "admin" ? true : null }, "Run benchmark"),
      me.role !== "admin" ? el("span", { class: "metric-note", style: "align-self:center;" }, "admin key required") : null),
    el("p", { class: "metric-note", style: "margin-top:8px;" },
      "Honest interpretation: these families co-evolve with the engine, so high detection shows the checks work as designed — it is not a claim of universal safety. The red-team loop exists to break this number."));

  host.replaceChildren(el("div", { class: "page-enter" }, toolbar,
    el("div", { style: "margin-top:12px;" }, resultBox)));
}

function benchReport(report) {
  const metric = (label, value, tone = "") =>
    el("div", { class: `card metric tone-${tone}` },
      el("div", { class: "metric-label" }, label),
      el("div", { class: "metric-value" }, String(value)));
  const families = Object.entries(report.per_family).map(([label, stats]) => ({
    label, passed: stats.passed, total: stats.total,
  }));
  return el("div", {},
    el("div", { class: "grid grid-4" },
      metric("Scenarios", report.total, "accent"),
      metric("Detection rate", `${(report.detection_rate * 100).toFixed(1)}%`,
        report.false_negatives === 0 ? "no misses" : `${report.false_negatives} misses`, "allow"),
      metric("False positives", `${(report.false_positive_rate * 100).toFixed(1)}%`,
        `${report.false_positives} of ${report.benign} benign`, report.false_positives === 0 ? "allow" : "block"),
      metric("p95 latency", `${report.latency_p95_ms}ms`, `p50 ${report.latency_p50_ms}ms · p99 ${report.latency_p99_ms}ms`, "accent")),
    el("div", { class: "card", style: "margin-top:12px;" },
      el("h3", { class: "card-title" }, "Family pass rates"),
      barRows(families)),
    report.failures.length > 0 ? el("div", { class: "card" },
      el("h3", { class: "card-title" }, `Failures (${report.failures.length})`),
      el("table", { class: "data" },
        el("thead", {}, el("tr", {}, el("th", {}, "Scenario"), el("th", {}, "Family"), el("th", {}, "Why"))),
        el("tbody", {}, report.failures.slice(0, 20).map((f) =>
          el("tr", {},
            el("td", { class: "mono" }, f.scenario_id),
            el("td", { class: "mono" }, f.family),
            el("td", { style: "color:var(--block);" }, f.failure_reason)))))) : null,
  );
}

/* ------------------------------------------------------------------ */
/* Demos                                                                */
/* ------------------------------------------------------------------ */

async function demo({ host, app }) {
  app.setTitle("Demos", "Reproducible sandbox attacks — no real purchasing, no real network");
  const demos = [
    {
      id: "intent_divergence",
      title: "Intent divergence via indirect prompt injection",
      text: "The human authorized 100 Lenovo laptops at ₹10,00,000 to Chennai. A malicious page tells the agent to buy 500 Apple laptops for ₹75,00,000 shipped to Mumbai. Watch the firewall block it with the full reasoning chain.",
    },
    {
      id: "trajectory_credential_harvest",
      title: "Trajectory attack: credential harvest",
      text: "Every action looks fine individually — read a page, send an email. The sequence is a harvest pattern only trajectory analysis can see.",
    },
  ];
  host.replaceChildren(el("div", { class: "page-enter" },
    el("div", { class: "grid grid-2" }, demos.map((d) =>
      el("div", { class: "card" },
        el("h3", { class: "card-title" }, d.title),
        el("p", { style: "color:var(--text-2);font-size:13px;" }, d.text),
        el("button", { class: "btn btn-primary btn-sm", type: "button",
          onclick: async (event) => {
            const target = document.getElementById(`demo-${d.id}`);
            target.replaceChildren(el("div", { class: "loading" }, "running …"));
            try {
              const transcript = await api.post(`/api/v1/demo/${d.id}/run`);
              target.replaceChildren(transcriptView(transcript));
            } catch (err) { target.replaceChildren(el("div", { class: "error-box" }, err.message)); }
          } }, "Run demo"),
        el("div", { id: `demo-${d.id}`, style: "margin-top:12px;" })))),
  ));
}

function transcriptView(transcript) {
  return el("div", {},
    el("div", { class: "decision-head" },
      decisionBadge(transcript.outcome === "block" ? "block" : transcript.outcome),
      el("strong", {}, " outcome")),
    el("p", { class: "metric-note", style: "margin-top:6px;" }, transcript.story),
    el("div", { class: "timeline", style: "margin-top:10px;" },
      transcript.steps.map((step) => el("div", {
        class: `tl-step ${step.decision === "allow" ? "ok" : step.decision === "escalate" ? "warn" : "bad"}`,
      },
        el("span", { class: "tl-dot" }, step.decision === "allow" ? "✓" : step.decision === "escalate" ? "!" : "✗"),
        el("div", { class: "decision-head" },
          el("span", { class: "tl-title" }, `${step.seq}. ${step.title}`),
          decisionBadge(step.decision)),
        (step.reasons || []).length
          ? el("div", { class: "reasons" }, step.reasons.map((r) => el("span", { class: "reason" }, r)))
          : null,
      ))),
    transcript.explanation?.authorized
      ? el("div", { class: "authorized-vs" },
          el("span", {}, "Authorized: ", el("b", {}, transcript.explanation.authorized)),
          el("span", {}, "Requested: ", el("b", {}, transcript.explanation.requested || "—")))
      : null,
  );
}

/* ------------------------------------------------------------------ */
/* Settings                                                             */
/* ------------------------------------------------------------------ */

async function settings({ host, app }) {
  app.setTitle("Settings", "Connection and deployment information");
  let me = null;
  try { me = await api.get("/api/v1/me"); } catch { me = null; }
  let tools = [];
  try { tools = (await api.get("/api/v1/tools")).tools; } catch { tools = []; }

  host.replaceChildren(el("div", { class: "page-enter" },
    el("div", { class: "card" },
      el("h3", { class: "card-title" }, "Connection"),
      me ? el("dl", { class: "kv" },
        el("dt", {}, "Organization"), el("dd", {}, me.org_id),
        el("dt", {}, "Principal"), el("dd", {}, me.principal_id),
        el("dt", {}, "Key role"), el("dd", {}, me.role),
        el("dt", {}, "Key ID"), el("dd", {}, me.key_id)) 
      : el("p", { class: "metric-note" }, "No API key configured — use the API key button in the top bar."),
      el("p", { class: "metric-note", style: "margin-top:10px;" },
        "Keys are hashed server-side (SHA-256); plaintext is shown once at creation. Role model: viewer < agent < admin.")),
    el("div", { class: "card" },
      el("h3", { class: "card-title" }, "Registered tools (sandbox)"),
      el("div", {}, tools.map((tool) => el("div", { style: "margin-bottom:8px;" },
        el("span", { class: "chip" }, el("strong", {}, tool.name)),
        tool.operations.map((op) => el("span", { class: "chip" }, `${op}`)),
        el("div", { class: "tree-detail", style: "margin-top:2px;" }, tool.description))))),
    el("div", { class: "card" },
      el("h3", { class: "card-title" }, "About this build"),
      el("p", { class: "metric-note" },
        "IntentGuard 0.1.0 — all tools shown are deterministic mocks in a sandbox (labeled MOCK). No external services are contacted by the demos or benchmarks."),
      el("p", { class: "metric-note" },
        "Docs: ARCHITECTURE.md · SECURITY_MODEL.md · ATTACKBENCH.md · THREAT_MODEL.md")),
  ));
}

export const PAGES = {
  overview, firewall, intents, policies, capabilities,
  sessions, approvals, audit, attackbench, demo, settings,
};
