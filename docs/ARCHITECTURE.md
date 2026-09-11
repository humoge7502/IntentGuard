# IntentGuard Architecture

Status: reflects the implemented system (v0.1.0). Every component listed here
exists in code and is exercised by tests.

## 1. The core thesis

```
HUMAN ── natural language ──► INTENT COMPILER ──► IntentSpec (versioned)
                                                        │
                                                        ▼  mint (intent ∩ policy)
                                              Capability (least privilege)
                                                        │
AGENT RUNTIME ── proposes action ──► ACTION FIREWALL ──┤
                                                        │
                        identity → capability → tool → operation →
                        parameters → policy → intent alignment →
                        context/taint → trajectory → risk → DECIDE
                                                        │
                              ┌─────────────────────────┼──────────────┐
                              ▼                         ▼              ▼
                            ALLOW                     ESCALATE        BLOCK
                              │                         │              │
                        tool executes          human approval bound    nothing
                        (once, audited)        to this exact digest    executes
```

**The security boundary is independent of any model.** The firewall is plain
deterministic Python. An LLM may propose; it can never authorize.

## 2. Component map (as implemented)

```
backend/intentguard/
├── core/           schemas (Pydantic, extra=forbid), enums, canonical JSON, ids, errors
├── intents/        RuleBasedIntentCompiler (deterministic), intent graph builder
├── policy/         PolicyEngine — denies block, limits cap, strictest layer wins
├── capabilities/   CapabilityManager — mints intent ∩ policy scopes
├── trajectory/     TrajectoryAnalyzer — replay, credential-harvest, degradation
├── risk/           RiskEngine — weighted signals → score/band/categories
├── approvals/      ApprovalService — digest-bound, single-use, expiring
├── audit/          AuditChain — per-org hash chain, optional Ed25519 signatures
├── firewall/       ActionFirewall (the pipeline) + EventBus (SSE fan-out)
├── tools/          ToolAdapter contract + 6 sandbox adapters + seeded content
├── storage/        IntentGuardStore protocol + SqlStore (SQLite/PostgreSQL)
├── demo/           the two reproducible attack narratives
├── attackbench/    schema, 23 scenario families, runner, metrics
└── api/            FastAPI app: versioned routes, key auth, roles, SSE, rate limit
frontend/           no-build control-plane SPA (ES modules, design-token CSS)
```

## 3. The enforcement pipeline (firewall/pipeline.py)

Every `evaluate()` runs the checks in order, collecting check results, reason
codes, and risk signals. Hard failures still let later checks run, so a single
decision explains *everything* that was wrong with it:

1. **identity** — session exists, is active, org matches, proposing agent owns
   the session (kills confused-deputy / impersonation).
2. **capability** — exists, belongs to the agent, active, unexpired.
3. **tool** — registered; operation known for that tool.
4. **operation** — inside the capability scope AND inside the intent's
   `allowed_operations` (kills tool abuse and excessive agency).
5. **parameters** — structural validation; unexpected fields rejected
   (kills parameter smuggling).
6. **policy** — deny rules block; limit rules cap financial exposure (minimum
   across layers wins).
7. **intent alignment** — budget/brand/destination/quantity/currency/time
   constraints from the compiled intent; failures append `INTENT_DIVERGENCE`.
   A high-impact financial action with **no budget constraint** is treated as
   uncertainty → ESCALATE, never silent allow.
8. **context / taint** — observations recorded by trusted tool adapters are
   compared against the action: externally-sourced amounts/brands/destinations
   that match a divergent request add taint signals; instruction-bearing
   content read recently raises the baseline risk.
9. **trajectory** — replay (same digest already executed), credential-harvest
   pattern (phishing content followed by messaging/banking tools), retry after
   repeated blocks, rapid high-impact cadence, cumulative risk; repeated
   hostile behavior **degrades the session** (high-impact then requires
   approval). Runs even on hard-failed actions so block-retry loops degrade.
10. **risk** — weighted signal sum → 0-100, bands low/moderate/high/critical.
11. **decide** —
    hard failure or critical risk → **BLOCK**;
    approval-required / high risk / uncertainty → **ESCALATE** (or ALLOW if an
    unconsumed grant exists for this exact digest);
    otherwise → **ALLOW**.

Every decision record carries: full check list, reason codes, risk breakdown,
`{intent, capability, policy_rules, compiler}` versions, the canonical action
digest, proposal metadata (for deterministic execution), and latency.

## 4. Trust boundaries

| Zone | Components | Trust |
|---|---|---|
| Trusted | firewall, policy/capability/risk engines, audit, store, API auth | the enforcement plane |
| Semi-trusted | intent compiler output (human-reviewed via UI), tool adapters | trusted code, bounded inputs |
| Untrusted | agent proposals, tool parameters, external content, HTTP bodies | validated at every boundary |

External content (web pages, documents, peer-agent messages) is summarized
into `Observation` objects **by our tool adapters**, never by the agent. Where
a third-party runtime supplies `context` observations, the firewall treats
them as best-effort signals: taint adds risk and can escalate, but hard
constraint enforcement never depends on agent-supplied context.

## 5. Data model

Organizations (tenant boundary) → principals → agents → sessions (1 intent,
1 capability, trajectory, degraded flag) → intents (versioned, constraints)
→ capabilities (versioned, scopes, budget, expiry) → decisions → approvals
→ audit events (per-org chain) → executions (idempotency + replay ledger).

Storage: SQLAlchemy Core; SQLite default, PostgreSQL via
`INTENTGUARD_DATABASE_URL`. Timestamps/decimals stored as ISO/numeric strings
for dialect portability (documented trade-off in DECISION_LOG).

## 6. Frontend

No-build ES-module SPA served at `/app` (design language in
docs/DESIGN_RESEARCH.md). Pages: Overview, live Firewall stream (SSE),
Approvals, Intents (+graph), Policies, Capabilities, Trajectories (+detail),
AttackBench runner, Demos, Audit (+chain verify), Settings. The API key stays
in `sessionStorage` per tab; every request is tenant-scoped by the key.

## 7. Extension points

- **New tool**: implement `ToolAdapter` (specs, param semantics, exposure,
  facts, execute) and register it — the firewall needs no changes.
- **New policy**: `POST /api/v1/policies` (layer, deny/limit).
- **New attack family**: add a generator in `attackbench/families.py`; the
  runner, metrics, UI, and CI regression gate pick it up automatically.
- **LLM-assisted compilation**: implement the compiler interface; its output
  flows through identical schema validation and the same firewall — the
  security posture does not depend on compiler intelligence.
- **Protocol adapters (MCP/A2A)**: normalize protocol tool-calls into
  `ActionProposal` and relay decisions; see docs/INTEGRATIONS_RESEARCH.md
  (designed, not yet implemented).
