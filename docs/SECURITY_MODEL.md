# IntentGuard Security Model

Companion: docs/THREAT_MODEL.md (attack analysis), docs/ATTACKBENCH.md
(evidence). This document states what the system guarantees, and — equally —
what it does not.

## 1. Security invariants (enforced, tested)

1. **No consequential side effect without a firewall decision.** Tools execute
   only through `engine.execute(decision_id)` on an ALLOW decision; execution
   is recorded once and replay of the same digest afterwards is blocked.
   (tests: test_firewall, test_trajectory)
2. **Authorization derives from human intent.** Capabilities are minted only
   from intents; the firewall checks operation, budget, brand, destination,
   quantity, currency, and time constraints. No API mints free-form
   capabilities. (tests: test_firewall)
3. **Uncertainty escalates, never silently allows.** High-impact financial
   actions without a budget constraint, approval-gated operations, high-risk
   bands → ESCALATE with a digest-bound approval request.
4. **Least privilege & narrowing-only policy.** Capability scopes come from
   the intent; deny rules block; limit rules cap at the strictest layer.
   Nothing in the system can widen a grant. (tests: test_firewall policy)
5. **Identity & tenant isolation.** The proposing agent must own the session;
   the session's org must match the key's org; every store query is
   org-scoped; cross-tenant reads behave as not-found; cross-tenant execution
   is impossible. (tests: test_tenant_isolation, test_api)
6. **Tamper-evident audit.** Per-org SHA-256 hash chains; any edit or deletion
   breaks verification. Optional Ed25519 signatures from a key held outside
   the DB defeat DB-only rewrite of signed events.
7. **Degradation under attack.** Repeated hostile actions degrade the session:
   further high-impact operations require human approval. Runs even when each
   individual action was already blocked. (tests: test_trajectory)
8. **Boundary validation everywhere.** Pydantic models with `extra=forbid`
   for HTTP bodies and domain objects; tool adapters reject unexpected
   parameters (kills parameter smuggling).
9. **Approvals cannot be reused.** Bound to one action digest, single-use,
   expiring, attributed. A grant for action A does not authorize action B.
   (tests: test_approvals, test_trajectory)

## 2. Honest limits

- **Deterministic compiler is narrow.** The rule-based compiler parses a
  constrained slice of natural language and records ambiguity instead of
  guessing. Intent text it cannot parse yields *fewer* capabilities (safe
  direction), but organizations must review compiled intents for high-value
  goals — the UI shows the graph precisely for this.
- **Audit is tamper-EVIDENT, not immutable.** An attacker with full database
  write access can rewrite the entire chain (and re-sign if they also steal
  the signing key). Mitigations on the roadmap: external hash anchoring,
  WORM storage. Do not claim immutability without those.
- **Taint analysis depends on trusted observations.** Reads that bypass
  IntentGuard's tool adapters (a third-party runtime fetching URLs itself)
  are invisible to taint tracking. Deploy with tools proxied through the
  platform for the full guarantee.
- **Constraint vocabulary is finite.** amount/brand/destination/quantity/
  time/approval/data-scope. A constraint that can't be expressed (e.g.
  "only from this vendor domain") can't be enforced yet — the pipeline
  architecture accepts new constraint kinds without structural change.
- **Mock tools are sandboxes.** No real purchasing/email/banking happens.
  Real integrations (§12 of the mission) are researched but not implemented;
  they must land behind the same firewall contract.
- **The API is not hardened for hostile internet exposure.** Key auth, rate
  limiting, and security headers exist; TLS termination, key rotation UI,
  per-IP limits, and audit-log retention automation are deployment concerns
  documented in DEPLOYMENT.md but not automated here.

## 3. Credential & secret handling

- API keys: random 32-byte urlsafe tokens, SHA-256 hashed at rest, shown
  once. Role model viewer < agent < admin enforced per route.
- No secrets in code or tests; `.env` git-ignored; `.env.example` documents
  every variable.
- Tool payloads are stored (decisions keep params for explainability) — do
  not put secrets in tool parameters; treat decision records as sensitive.

## 4. Rate limiting & abuse

In-memory sliding window per key (`INTENTGUARD_RATE_LIMIT_PER_MIN`, default
600/min), 429 on exceed. Single-process only — use a shared store (e.g. Redis)
when running replicas (roadmap).

## 5. Future work (tracked in TASKS.md)

TLS/termination guidance, key rotation & revocation UI, WORM audit anchoring,
Redis-backed rate limiting, Alembic migrations, CSP headers + SRI for the
dashboard, pen-test pass, MCP/A2A adapter implementations.
