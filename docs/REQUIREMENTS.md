# IntentGuard Requirements

Product and security requirements for v0.1.0, with verification status.
Legend: ✅ implemented + tested · ◐ partially implemented · ⬜ not started.

## R1 — Intent & authorization core
- R1.1 Compile natural-language goals into versioned structured intents ✅
- R1.2 Record ambiguity and conflicts instead of guessing ✅
- R1.3 Derive least-privilege capabilities from intent ∩ policy ✅
- R1.4 Capabilities: scoped, versioned, revocable, time-bounded ✅
- R1.5 Policy hierarchy with narrowing-only semantics ✅
- R1.6 Pluggable LLM-assisted compilation (same validation path) ⬜ (interface documented)

## R2 — Enforcement
- R2.1 Independent deterministic firewall decides before side effects ✅
- R2.2 ALLOW / BLOCK / ESCALATE with structured reason codes ✅
- R2.3 Intent alignment: budget, brand, destination, quantity, currency, time ✅
- R2.4 Uncertain high-impact actions escalate, never silently allow ✅
- R2.5 Tool/operation/parameter validation incl. unexpected-field rejection ✅
- R2.6 Capability revocation takes effect immediately ✅

## R3 — Trajectory security
- R3.1 Per-session trajectory tracking with per-step verdicts ✅
- R3.2 Replay detection on executed actions ✅
- R3.3 External-content taint analysis from trusted observations ✅
- R3.4 Multi-step attack patterns (credential harvest, §6 sequence) ✅
- R3.5 Cumulative risk + session degradation under repeated hostility ✅
- R3.6 Trajectory replay/inspection API + UI ✅

## R4 — Risk & explainability
- R4.1 Deterministic weighted risk scoring with bands ✅
- R4.2 Hard violations bypass scoring; scoring governs uncertainty ✅
- R4.3 Every decision: checks, reason codes, versions, latency ✅
- R4.4 Decision replay feasibility: stored proposal + versions ⬜ (data captured; re-run harness not built)

## R5 — Human approval
- R5.1 Escalation creates digest-bound approval requests ✅
- R5.2 Single-use, expiring, attributed grants ✅
- R5.3 Grant cannot transfer to a different action ✅
- R5.4 Approval delivery (email/Slack) ⬜ (UI + API polling only)

## R6 — Audit & identity
- R6.1 Hash-chained per-org audit events ✅
- R6.2 Optional Ed25519 signing ✅
- R6.3 Verification API + dashboard ✅
- R6.4 Full attribution (who/which agent/which intent/…/why) ✅
- R6.5 Agent reputation signals (architecture reserved: trust_score field, never security-authoritative) ◐

## R7 — Platform
- R7.1 Versioned REST API with key auth + roles ✅
- R7.2 Multi-tenancy with enforced isolation ✅
- R7.3 Rate limiting ✅ (in-memory; Redis ⬜)
- R7.4 SSE live decision stream ✅
- R7.5 PostgreSQL support ✅ (same schema; migrations via Alembic ⬜ — create_all for MVP)
- R7.6 Docker packaging ✅ (image defined; local daemon verification below)
- R7.7 CI pipeline ✅ (GitHub Actions: lint, tests, AttackBench gate, latency smoke, audit, docker build)

## R8 — Adversarial evaluation
- R8.1 AttackBench with ≥20 attack families + benign families ✅ (23 families)
- R8.2 Real metrics: detection, FP, escalation, latency ✅
- R8.3 CI regression gate on detection/FP floors ✅
- R8.4 Thousands of scenarios ◐ (208 distinct parameterizations; generator architecture scales, padding count without new coverage rejected — see BENCHMARKS.md)
- R8.5 Red-team loop with external red team ⬜ (internal adversarial pass done; findings fixed)

## R9 — Frontend
- R9.1 Security-console dashboard with meaningful visualizations ✅
- R9.2 Live firewall stream ✅
- R9.3 Intent graph, trajectory timeline, decision explain cards ✅
- R9.4 AttackBench UI, approvals, audit verification ✅
- R9.5 Responsive + keyboard + reduced-motion + AA contrast ✅ (token-verified; full a11y audit ⬜)
- R9.6 Demo narratives reproducible in UI ✅

## R10 — Real integrations
- R10.1 MCP adapter ⬜ (researched + designed: docs/INTEGRATIONS_RESEARCH.md)
- R10.2 A2A adapter ⬜ (researched)
- R10.3 GitHub/Slack/Gmail/AWS/Stripe sandbox ⬜ (auth models researched)

## R11 — Documentation
- R11.1 Setup/architecture/API/security/deployment docs ✅
- R11.2 Threat model + security model with honest limits ✅
- R11.3 Research: prior art, skills, integrations, design ✅ (see docs/)
- R11.4 Extension guides (add tool/policy/attack) ✅ (DEVELOPMENT.md)
