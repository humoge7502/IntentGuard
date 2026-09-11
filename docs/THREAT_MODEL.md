# IntentGuard Threat Model

Scope: the IntentGuard control plane, its mock-tool sandbox, API, and
dashboard. Adversaries are *simulated* in AttackBench; no real third parties
are targeted. Doc version: 2026-09-12, v0.1.0.

## 1. Assets

- A1 Human intent records and compiled constraints (authorization source of truth)
- A2 Capabilities (authorization artifacts)
- A3 Decision records & audit chain (non-repudiation, forensics)
- A4 API keys (tenant access)
- A5 The enforcement boundary itself (the thing everything else depends on)
- A6 Mock-tool state (orders/transfers — demonstrates what *would* be money)

## 2. Adversaries

| # | Adversary | Capability |
|---|---|---|
| AD1 | Malicious/compromised agent | controls proposals, parameters, tool choices; influenced by injected content |
| AD2 | External content attacker | controls web pages/documents/peer messages the agent reads (prompt injection) |
| AD3 | Rogue tenant | holds a valid API key for org B; wants org A's data or to act in org A |
| AD4 | Malicious insider (tenant admin) | admin key in one org; wants to forge/erase audit history in that org |
| AD5 | Network attacker | no credentials; probes the HTTP surface |
| AD6 | The proposing LLM itself | hallucinated/ manipulated outputs reaching the firewall |

## 3. STRIDE analysis (implemented mitigations in **bold**)

### Spoofing
- AD1 proposes actions as another agent → **identity check: agent must own the session** (IDENTITY_MISMATCH).
- AD2 content claims supervisory authority → **identity-claim observations raise risk**; the firewall never accepts authority claims from content.
- AD5 brute-forces keys → **256-bit random keys, hashed at rest, rate limited**.

### Tampering
- AD1 alters params after evaluation → **decisions embed proposal metadata; execution uses the stored proposal, not a new one**.
- AD4 edits audit rows → **hash chain breaks verification** (test proves detection at the exact seq).
- AD4 rewrites the whole chain → **detected only if unsigned or key compromised** — documented limit; external anchoring is roadmap.

### Repudiation
- AD1 denies the blocked action → **every decision hash-chained with actor, digest, reasons, risk**.
- AD4 grants itself approvals → **grants recorded with approver identity in the chain**.

### Information disclosure
- AD3 reads org A intents/decisions → **every store query org-scoped; HTTP 404s; tests enforce**.
- AD5 probes errors → **uniform error envelope, no stack traces**; security headers set.

### Elevation of privilege
- AD1 uses another agent's capability → **capability↔agent binding checked** (CAPABILITY_AGENT_MISMATCH).
- AD1 chains allowed actions into an attack → **trajectory rules + cumulative risk + session degradation**.
- AD1 replays an executed action → **execution-ledger replay block**.
- AD2 inflates amounts via injected content → **constraint checks use intent, not content; matching external amounts add taint and escalate/block**.

### Denial of service
- AD1 floods evaluate → **per-key rate limit**; decisions are O(1)-ish (indexes on digest/session/org).
- AD5 floods unauthenticated → **rate limiter applies pre-auth by key material**; production deployments should add edge limits (DEPLOYMENT.md).

## 4. Attack-surface inventory

- HTTP API `/api/v1/*` — key auth, role gates, strict bodies, org scoping.
- SSE `/api/v1/events/stream` — key via header or query param (EventSource
  limitation; documented), read-only stream.
- Static dashboard `/app` — no privileged browser APIs used; key in
  sessionStorage (tab-scoped, cleared on tab close).
- Tool adapters — sandboxed mocks; no network egress by construction
  (pseudo-scheme URIs, *.example hosts).
- Store — SQLite/Postgres; parameterized queries via SQLAlchemy (no string SQL).

## 5. Residual risks (accepted for MVP, tracked)

R1 Audit immutability vs full-store attacker (roadmap: anchoring).
R2 In-memory rate limiter is per-process (roadmap: Redis).
R3 Deterministic compiler coverage gaps → over-strictness, not over-permissiveness; still requires human review for high-value intents.
R4 Observation fidelity depends on proxied reads (see SECURITY_MODEL §2).
R5 No automated dependency/vulnerability scanning run locally — CI defines pip-audit job (runs on push).
