# Integrations Research: MCP, A2A, Agent Identity

Research date: **2026-09-12**. Sources verified by direct fetch on that date
(marked ✅); anything not verified is marked ⚠️ UNVERIFIED. This document is
technical research; it makes no compatibility claims beyond what the cited
sources state.

## 1. Model Context Protocol (MCP) ✅

Source: https://modelcontextprotocol.io/specification/latest (fetched
2026-09-12; current schema revision **2026-07-28**, `schema.ts` path visible
on page).

- JSON-RPC 2.0; roles: Host (LLM app) / Client (connector) / Server (context,
  tools). Primitives: Resources, Prompts, Tools; client-side Elicitation.
- Transports: stdio (local) and HTTP-based ("Streamable HTTP"); authorization
  applies to HTTP transports only — stdio SHOULD use environment credentials.
- Security posture (normative "Security and Trust & Safety" section): user
  consent and control; hosts MUST obtain consent before tool invocation;
  **tool descriptions/annotations are untrusted unless from a trusted
  server** — this aligns exactly with IntentGuard's "external content is
  never authoritative" boundary.
- Extensions (opt-in): Tasks (async long-running ops), Skills over MCP,
  MCP Apps (inline UI).

### Authorization ✅
Source: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization

- MCP server = **OAuth 2.1 resource server**; MCP client = OAuth 2.1 client;
  authorization server external (discovered via **RFC 9728 Protected Resource
  Metadata**, which MCP servers MUST implement).
- Clients MUST implement **RFC 8707 resource indicators** (token audience
  binding: tokens valid only for the intended MCP server), PKCE, issuer
  validation (RFC 9207). Step-up authorization flows defined for
  insufficient-scope (403 + `WWW-Authenticate: insufficient_scope`).
- Dynamic Client Registration (RFC 7591) deprecated in favor of Client ID
  Metadata Documents.

### Where IntentGuard plugs in (design; not implemented)

The natural enforcement point is a **mediating MCP server**: the agent's host
connects to IntentGuard's MCP facade, which exposes the *union of upstream
tool catalogs* but routes every `tools/call` through `firewall.evaluate`
before proxying to the real server, and through `firewall.execute` after an
ALLOW. Capability scopes map naturally to (server, tool, operation) triples;
MCP scopes/OAuth map to IntentGuard identity (agent id from the token's
subject + client-id metadata). Because the firewall's input is already the
normalized `ActionProposal`, the adapter is thin:

```
agent host ──MCP──► IntentGuard MCP facade ──evaluate()──► ALLOW ──► upstream MCP server
        ◄──result── (BLOCK: error with reason codes; ESCALATE: elicitation-style
                     request tied to the approval digest)
```

ESC diagonal: MCP Elicitation is a client-side primitive; an ESCALATE decision
can be surfaced as a tool-call error carrying `approval_id` + `action_digest`,
with the dashboard/API as the approval surface (works with hosts that don't
implement elicitation). MVP vs later: MVP = stdio facade over one upstream
server with static tool→capability mapping; later = multi-server aggregation,
OAuth-anchored identity, Tasks extension mapping to sessions.

## 2. Agent2Agent (A2A) ✅ (status), ⚠️ (version number)

Source: https://github.com/a2aproject/A2A (fetched 2026-09-12).

- Open protocol for **opaque agent-to-agent** interoperability: agents
  collaborate "as agents, not just as tools", hiding internal state/memory/
  tools. **Linux Foundation** open-source project, contributed by Google,
  Apache-2.0. SDKs: Python, Go, JS, Java, .NET, Rust.
- Core concepts: **Agent Card** (capability + connection discovery), Tasks
  (long-running collaboration lifecycle), rich data exchange (text/files/
  structured JSON). Transport: JSON-RPC 2.0 over HTTPS, SSE streaming, async
  push notifications. Positioned as **complementary to MCP**.
- Exact spec version number was not visible on the fetched pages ⚠️ — verify
  at https://a2a-protocol.org/latest/specification/ before implementation.

### IntentGuard fit (design)

Cross-agent escalation is already a first-class denial
(`CAPABILITY_AGENT_MISMATCH`, `IDENTITY_MISMATCH`, A2A-manipulation family).
The adapter design: IntentGuard sits at the *edge* of each participating
agent — inbound Agent Card exchange declares capabilities; every outbound
task/send request is an `ActionProposal` (tool `a2a`); inbound messages are
observations (`contains_identity_claims` is exactly the peer-message attack
we simulate). Delegation chains map to IntentGuard's principal→agent
ownership graph: an agent may only delegate a subset of its own scopes.

## 3. Agent identity options

| Anchor | Status | Notes |
|---|---|---|
| MCP OAuth (subject + client-id metadata) ✅ | current | identity = token subject at the resource server; audience-bound (RFC 8707) |
| SPIFFE/SPIRE ⚠️ UNVERIFIED (not re-checked today) | mature | workload identity via SVIDs; strong in k8s, heavier ops |
| Cloud workload identity (AWS STS / GCP ID tokens) ⚠️ | mature | per-cloud; maps to principal model |
| IntentGuard native (API key → principal → agent) ✅ | implemented | MVP answer; upgrade path to OAuth |

MVP uses native identity; the ActionProposal schema carries agent identity
externally to any of the above anchors.

## 4. Integration surfaces (later phases, auth models)

- **GitHub**: GitHub App (installation tokens, fine-grained permissions) over
  PATs; write-side ops to gate: `issues.write`, `pull_requests.write`,
  `contents.write`, `workflows`.
- **Slack**: app with bot token + granular scopes; gate `chat:write`,
  file uploads, admin ops.
- **Gmail**: OAuth with least-privilege scopes; gate send/forward/label
  mutations; read scope is the exfil surface — data-access constraints apply.
- **AWS**: IAM role assumption with session policies; gate by IAM action
  prefix; STS tags can carry IntentGuard session id for CloudTrail joins.
- **Stripe**: test/sandbox keys only until formally reviewed; gate
  `charges`, `transfers`, `payouts`; idempotency keys align with IntentGuard
  action digests.

## 5. Recommendation (one thing that matters most)

Keep the firewall **protocol-independent** (already true): adapters translate
wire protocols into `ActionProposal` and relay `Decision`. Everything else —
MCP facade, A2A edge, REST — is normalization. Do not couple scope/identity
semantics to any single protocol; mint IntentGuard capabilities from
protocol-agnostic intent, and let adapters prove the mapping.

## Sources (all fetched 2026-09-12)

- MCP spec overview: https://modelcontextprotocol.io/specification/latest
- MCP authorization: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization
- A2A project: https://github.com/a2aproject/A2A
- OWASP Gen AI Top 10 (2025): https://genai.owasp.org/llm-top-10/ (Excessive
  Agency = LLM06, Prompt Injection = LLM01 — threat-model cross-reference)
