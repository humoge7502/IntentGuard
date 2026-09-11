# IntentGuard

**Runtime authorization and security control plane for autonomous AI agents.**

> An autonomous agent should never be allowed to perform an externally
> consequential action merely because the LLM decided the action looks
> reasonable. Every consequential action is evaluated against the human's
> compiled intent, scoped capabilities, policy, execution context, and
> accumulated trajectory by an independent enforcement layer — **before**
> the side effect occurs.

```
LLM proposes  →  IntentGuard decides  →  tool executes only on ALLOW
                                             ├─ ALLOW     within intent, capability, policy, context, trajectory
                                             ├─ BLOCK     hard violation (constraint, policy, identity, replay, …)
                                             └─ ESCALATE  uncertain or gated → human approval bound to one exact action
```

## Quick start

Prerequisites: Python 3.11+ (3.13 verified).

```bash
# 1. backend + venv
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"        # Windows
# .venv/bin/pip install -e ".[dev]"          # Linux/macOS

# 2. start the API + dashboard (bootstrap prints a one-time admin key)
INTENTGUARD_SQLITE_PATH=../data/intentguard.db \
  .venv/Scripts/python -m uvicorn --factory intentguard.api.app:create_app --port 8400

# 3. open the control plane and paste the admin key
#    http://127.0.0.1:8400/app/
```

Or with Docker (daemon required):

```bash
docker compose up            # SQLite volume; optional postgres profile documented inside
```

## Five-minute tour

```bash
KEY=<the ig_… key printed at bootstrap>
BASE=http://127.0.0.1:8400/api/v1

# compile a human goal into a verifiable intent
curl -X POST $BASE/intents -H "X-API-Key: $KEY" \
  -d '{"text": "Buy 100 Lenovo laptops with a total budget of 10,00,000 INR and deliver them to Chennai"}'

# register an agent, start a session (mints the least-privilege capability)
curl -X POST $BASE/agents   -H "X-API-Key: $KEY" -d '{"name": "procurement-agent"}'
curl -X POST $BASE/sessions -H "X-API-Key: $KEY" \
  -d '{"agent_id": "<agt_…>", "intent_id": "<int_…>"}'

# propose an action: the firewall decides BEFORE execution
curl -X POST $BASE/firewall/evaluate -H "X-API-Key: $KEY" -d '{
  "session_id": "<ses_…>", "agent_id": "<agt_…>",
  "tool": "shopping_api", "operation": "purchase",
  "params": {"item": "laptop", "brand": "Apple", "unit_price": "15000",
             "quantity": 500, "currency": "INR", "destination": "Mumbai"}}'
# → {"decision": "block", "reasons": ["AMOUNT_LIMIT_EXCEEDED", "QUANTITY_EXCEEDED",
#     "BRAND_NOT_ALLOWED", "DESTINATION_NOT_ALLOWED", "INTENT_DIVERGENCE"], …}
```

In the dashboard: **Demos** runs the full attack narrative in the UI,
**AttackBench** runs the adversarial benchmark against the live firewall.

## What's here

| Layer | Status | Notes |
|---|---|---|
| Intent compiler | ✅ deterministic v1 | NL → constraints/operations/ambiguities; strict-by-default |
| Policy engine | ✅ | narrowing-only: denies block, limits cap; permissive never widens |
| Capabilities | ✅ | least-privilege, scoped, versioned, revocable, time-bounded |
| Action Firewall | ✅ | 11-stage pipeline; ALLOW/BLOCK/ESCALATE with reason codes |
| Trajectory security | ✅ | taint tracking, replay, credential-harvest patterns, session degradation |
| Risk engine | ✅ deterministic | weighted signals → 0-100 score & bands; hard violations bypass |
| Approvals | ✅ | bound to one action digest, single-use, expiring |
| Audit | ✅ | SHA-256 hash chain + optional Ed25519 signing; tamper-evident |
| Multi-tenancy | ✅ | every object org-scoped; cross-tenant tests enforced |
| API | ✅ | FastAPI, versioned `/api/v1`, API keys (hashed), roles, rate limit |
| Dashboard | ✅ | live SSE decision stream, intent graph, trajectories, AttackBench UI |
| Independent audit | ✅ round 2 | 6 defects found & fixed with regression tests — docs/AUDIT.md |
| AttackBench | ✅ | 23 families / 208+ scenarios; regression-gated in CI |
| Mock tools | ✅ | shopping/banking/email/web/file/A2A-inbox — all sandboxed |
| Tests | ✅ 76 passing | unit, integration, security, tenant isolation, adversarial, concurrency-race |
| Real integrations (MCP/A2A/GitHub/…) | 🚫 not started | adapter architecture researched; see docs/INTEGRATIONS_RESEARCH.md |

Honesty labels: everything above marked ✅ is verified by tests in this repo.
Mock tools are labeled **MOCK** in code and UI. No benchmark numbers in this
repo are fabricated — every figure quotes a real run (see `docs/BENCHMARKS.md`).

## Documentation

| Doc | Contents |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | components, data flow, trust boundaries |
| [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) | threat model, guarantees and their limits |
| [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) | product + security requirements |
| [docs/API.md](docs/API.md) | endpoint reference |
| [docs/ATTACKBENCH.md](docs/ATTACKBENCH.md) | attack families, how to add scenarios |
| [docs/BENCHMARKS.md](docs/BENCHMARKS.md) | verified benchmark runs + honest interpretation |
| [docs/THREAT_MODEL.md](docs/THREAT_MODEL.md) | STRIDE-style analysis |
| [docs/DECISION_LOG.md](docs/DECISION_LOG.md) | key decisions with rationale |
| [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) | local setup, testing, extending |
| [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) | Docker, env vars, production notes |
| [docs/PRIOR_ART.md](docs/PRIOR_ART.md) | patent/academic/industry landscape research |
| [docs/SKILLS_RESEARCH.md](docs/SKILLS_RESEARCH.md) | agent-skills ecosystem assessment |
| [docs/INTEGRATIONS_RESEARCH.md](docs/INTEGRATIONS_RESEARCH.md) | MCP/A2A/identity research |
| [docs/DESIGN_RESEARCH.md](docs/DESIGN_RESEARCH.md) | UI design language derivation |
| [docs/PROJECT_INVENTORY.md](docs/PROJECT_INVENTORY.md) | repository inventory |
| [docs/TASKS.md](docs/TASKS.md) | task ledger with statuses |

## Security posture (short version)

- The firewall is **independent of any LLM** — deterministic code only. An LLM
  can propose; it can never authorize.
- All boundary data (agent proposals, tool params, HTTP bodies) is
  schema-validated with `extra="forbid"`.
- High-impact operations without the matching intent constraint **escalate** —
  uncertainty never silently allows.
- Audit events are hash-chained per organization; tampering is detectable via
  `POST /api/v1/audit/verify`. Not immutable against full-store rewrites —
  documented honestly in SECURITY_MODEL.md.
- The deterministic compiler is transparent but narrow; production deployments
  should pair it with review workflows for high-value intents.

See [docs/SECURITY_MODEL.md](docs/SECURITY_MODEL.md) for the full model and
[SECURITY.md](SECURITY.md) for reporting policy.

## License

MIT — see [LICENSE](LICENSE).
