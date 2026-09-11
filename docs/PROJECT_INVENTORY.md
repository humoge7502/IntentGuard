# Project Inventory

Generated 2026-09-12 at build completion. Greenfield start (empty directory
at Phase 0); everything below was created in this build.

## Repository layout

```
IntentGuard/
├── README.md                    entry point, quick start, honest status table
├── LICENSE                      MIT
├── SECURITY.md                  vulnerability reporting policy
├── CONTRIBUTING.md              contribution workflow
├── .env.example                 every documented env var
├── .gitignore / .dockerignore
├── Dockerfile                   python:3.12-slim, healthcheck, verified build
├── docker-compose.yml           app + optional postgres profile
├── .github/workflows/ci.yml     lint, tests, AttackBench gate, latency smoke,
│                                pip-audit, docker build + smoke
├── docs/                        15 documents (see README table)
├── frontend/                    no-build control-plane SPA
│   ├── index.html
│   └── assets/css/{tokens,main}.css, assets/js/{app,api,helpers,pages}.js
└── backend/
    ├── pyproject.toml           deps, ruff, pytest config
    ├── scripts/bench_firewall.py
    ├── tests/                   9 files, 68 tests
    └── intentguard/
        ├── engine.py            façade wiring the whole control plane
        ├── config.py            env settings
        ├── core/                schemas, enums, canonical JSON, ids, errors
        ├── intents/             compiler (deterministic), graph builder
        ├── policy/              narrowing-only policy engine
        ├── capabilities/        capability minting
        ├── trajectory/          replay/pattern/cumulative analysis
        ├── risk/                weighted signal scoring
        ├── approvals/           digest-bound approval service
        ├── audit/               hash chain + optional Ed25519
        ├── firewall/            the pipeline + SSE event bus
        ├── tools/               adapter contract + 6 sandbox tools + seeded content
        ├── storage/             store protocol + SQLAlchemy implementation
        ├── attackbench/         schema, 23 families, runner, metrics
        ├── demo/                two reproducible attack narratives
        └── api/                 FastAPI routes, auth, SSE, app factory
```

## Dependencies (runtime)

| Package | License | Why |
|---|---|---|
| fastapi | MIT | HTTP API + OpenAPI |
| uvicorn | BSD-3 | ASGI server |
| pydantic | MIT | strict boundary schemas |
| sqlalchemy | MIT | storage (SQLite/PostgreSQL) |
| PyYAML | MIT | config/scenario loading headroom |
| httpx | BSD-3 | test client |
| cryptography | Apache-2.0/BSD | Ed25519 audit signing |

Dev: pytest (MIT), ruff (MIT). No other runtime dependencies — the frontend
has zero build/runtime packages (system fonts + two Google Fonts links).

## Test inventory (68)

| File | Covers |
|---|---|
| test_compiler.py | NL parsing, ambiguity, determinism, safe defaults |
| test_firewall.py | constraint/policy/identity/capability enforcement (17) |
| test_trajectory.py | taint, credential-harvest, replay, degradation, approval interplay |
| test_approvals.py | lifecycle, single-use, expiry, binding |
| test_audit.py | chain verify, tamper/delete detection, signing |
| test_tenant_isolation.py | cross-org store/API/firewall isolation |
| test_api.py | HTTP auth, roles, endpoints, headers, rate limit, demos, SSE bus |
| test_attackbench.py | detection ≥95%, FP ≤2%, family floors ≥80% |

## Known gaps (pointers)

Real integrations, LLM-assisted compiler, Alembic migrations, Redis rate
limiting, WORM audit anchoring, a11y audit, load harness — tracked in
docs/REQUIREMENTS.md and docs/TASKS.md.
