# TASKS — Definition of Done ledger

Statuses: DONE (verified by tests or a recorded run) · PARTIAL (implemented
with named gaps) · BLOCKED (external blocker documented) · TODO.

## Final acceptance audit — 2026-09-12

### Phase 0–5: foundations
- [x] DONE Repository fully inspected (empty dir → inventory written)
- [x] DONE Architecture documented (docs/ARCHITECTURE.md)
- [x] DONE Requirements documented (docs/REQUIREMENTS.md)
- [x] DONE Technical roadmap (REQUIREMENTS R1–R11 + DECISION_LOG)
- [x] DONE Threat model (docs/THREAT_MODEL.md)
- [x] DONE Security model with honest limits (docs/SECURITY_MODEL.md)

### Core engine
- [x] DONE Intent Compiler (deterministic v1; ambiguity recorded; LLM path documented)
- [x] DONE Intent representation + versioning
- [x] DONE Intent graph (API + UI tree)
- [x] DONE Policy engine (narrowing-only, layered)
- [x] DONE Capability system (scoped, versioned, revocable, expiring)
- [x] DONE Agent identity (principal → agent → session attribution)
- [x] DONE Action Firewall (11-stage pipeline; independent of any LLM)
- [x] DONE Intent/action verification (constraint checks with reason codes)
- [x] DONE Trajectory tracking + risk analysis (replay, taint, patterns, degradation)
- [x] DONE Risk engine (deterministic weighted signals, bands)
- [x] DONE ALLOW / BLOCK / ESCALATE (with escalation → digest-bound approvals)
- [x] DONE Capability revocation (immediate effect, audited)
- [x] DONE Audit trail (hash chain + optional Ed25519; verify API + UI)
- [x] DONE Cryptographic integrity (SHA-256 chaining; honest immutability limits stated)
- [x] DONE Approvals (single-use, expiring, non-transferable)

### Evaluation
- [x] DONE Mock tools (6 adapters, fault injection, sandbox-only content)
- [x] DONE AttackBench (23 families, 208 scenarios, runner + metrics + UI)
- [x] DONE Adversarial suite + regression gate in CI floors
- [x] PARTIAL Scenario count: 208 distinct parameterizations (mission aspiration
      "thousands" rejected as padding — DECISION_LOG D12)
- [x] DONE Demo scenarios (§61 divergence, §62 trajectory) reproducible in UI/API

### Platform
- [x] DONE API (versioned, key auth, roles, rate limit, SSE, OpenAPI docs)
- [x] DONE Multi-tenancy boundaries + tests (critical-failure treatment per §36)
- [x] DONE Database (SQLAlchemy; SQLite default / Postgres URL; create_all MVP)
- [ ] PARTIAL Migrations: Alembic not wired (REQUIREMENTS R7.5)
- [x] DONE Observability: decision/audit records + event stream; structured
      logging of every enforcement event (full metrics/tracing stack TODO)
- [x] DONE CI (GitHub Actions: lint, tests, AttackBench gate, latency smoke,
      pip-audit, docker build+smoke) — defined; executes on GitHub push
      (not executable in this workspace; Docker steps verified locally)
- [x] DONE Dependency scanning (pip-audit job; local runtime deps reviewed —
      docs/DEPENDENCIES.md)
- [x] DONE Security scanning posture (ruff security-relevant rules; pip-audit;
      CodeQL not configured — TODO)

### Frontend
- [x] DONE Dashboard complete (browser-verified: overview, live stream, intents,
      graph, policies, capabilities, trajectories, approvals, audit, AttackBench,
      demos, settings)
- [x] DONE Responsive + keyboard + reduced motion + AA-contrast tokens
- [ ] PARTIAL Formal accessibility audit (manual checks done; automated a11y
      suite not run)

### Performance
- [x] DONE Firewall latency benchmark measured (p50 8.5ms / p95 15.5ms /
      p99 21.4ms, n=2000) + regression smoke in CI
- [ ] TODO Load/concurrency harness

### Infrastructure
- [x] DONE Docker image + compose (build + container smoke verified locally:
      health 200, dashboard 200, bootstrap key printed)
- [x] DONE .env.example, seed/bootstrap flow, health checks
- [x] DONE Deployment procedure documented (docs/DEPLOYMENT.md)

### Research
- [x] DONE Skills research (docs/SKILLS_RESEARCH.md — sources fetched 2026-09-12)
- [x] DONE GitHub ecosystem research (same doc + INTEGRATIONS_RESEARCH.md)
- [x] DONE Third-party license review (docs/DEPENDENCIES.md)
- [x] DONE Prior-art research (docs/PRIOR_ART.md — patent databases marked as
      not systematically searched; professional search required for counsel)
- [x] DONE MCP/A2A research (docs/INTEGRATIONS_RESEARCH.md — spec 2026-07-28
      verified)

### Integrations
- [ ] BLOCKED Real MCP/A2A/GitHub/Slack/Gmail/AWS/Stripe integrations — adapter
      architecture designed (INTEGRATIONS_RESEARCH §1-4); no sandbox accounts
      provisioned in this environment. No fake integrations were built (§47).

### Governance
- [x] DONE Git history with meaningful commits; no destructive operations
- [x] DONE No secrets committed (keys generated at runtime only; .env ignored)
- [x] DONE No fake integrations / no fabricated benchmark numbers (labeled)
- [x] DONE Documentation set complete (15 docs)

## Known P0/critical security defects
None known at time of audit. Resolved during build (each has a regression
test): trajectory org-scoping defect (degradation inert), replay-bind-to-
authorization overreach, approval-dedupe O(n²) hotspot, audit signing verify
key type, hidden-attribute CSS override in the dashboard.

## Backlog (next milestones)
1. MCP facade adapter (design ready) → real integration with one upstream server
2. Alembic migrations + Postgres CI job
3. Redis-backed rate limiting + multi-replica SSE fan-out
4. WORM/external anchoring for audit immutability
5. LLM-assisted intent compilation behind the same validation path
6. Automated a11y + E2E browser suite in CI
7. Load harness + sustained-throughput benchmark
8. Reputation signals (architecture reserved: trust_score) behind a feature flag
