# Development Guide

## Setup

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"     # Windows
# or .venv/bin/pip install -e ".[dev]"

cp ../.env.example ../.env                 # optional; env vars work directly

# run API + dashboard (prints a one-time bootstrap admin key)
INTENTGUARD_SQLITE_PATH=../data/intentguard.db \
  .venv/Scripts/python -m uvicorn --factory intentguard.api.app:create_app --port 8400
# dashboard: http://127.0.0.1:8400/app/
```

## Tests

```bash
.venv/Scripts/python -m pytest tests/          # full suite (≈18s)
.venv/Scripts/python -m pytest tests/test_attackbench.py   # adversarial gate
.venv/Scripts/python -m ruff check intentguard tests scripts
```

The suite uses in-memory SQLite; no services needed. Tenant-isolation,
audit-tamper, and replay tests are security regression tests — treat any
failure there as a P0.

## Lint / format

```bash
.venv/Scripts/python -m ruff check intentguard tests scripts
.venv/Scripts/python -m ruff format intentguard tests scripts   # optional
```

## Common tasks

### Add a tool
1. Subclass `ToolAdapter` (`intentguard/tools/base.py`): declare
   `specs` (operations + side-effect classes + required params) and
   `param_map` (semantic roles: brand/destination/quantity/amount/currency —
   these drive intent-constraint checks), implement `execute`.
2. Register in `tools/__init__.py: default_registry()`.
3. Add benign scenarios exercising it to AttackBench.

The firewall and capability minting pick the tool up automatically — no
firewall changes needed.

### Add a constraint kind
1. Model in `core/schemas.py` (discriminated union member with `kind`).
2. Enforce in the intent-alignment stage of `firewall/pipeline.py`.
3. Optionally teach `intents/compiler.py` to recognize it in NL.
4. Add firewall + AttackBench coverage.

### Add an attack family
See docs/ATTACKBENCH.md §"Adding a family". If it detects a real bypass:
fix the engine first, then the family becomes the permanent regression test.

### Add an API route
`intentguard/api/routes.py`; choose the role dependency (`get_auth`,
`get_agent_role`, `get_admin`); org-scope every store call via
`auth.org_id` — never trust identifiers from the body for tenancy.

## Project conventions

- All boundary models: Pydantic, `extra="forbid"`.
- Reason codes and enums are stable wire identifiers — never renumber.
- Money via `Decimal` (string on the wire); timestamps UTC ISO-8601.
- No secrets in code; no network calls in the security core; mock tools only.
- Comments state constraints the code can't show, not narration.

## Debugging the firewall

Every decision persists its full check list. Fastest loop:

```python
d = engine.propose(...)
for check in d.checks: print(check.status.value, check.check, check.detail)
print(d.reasons, d.risk)
```

or watch `http://127.0.0.1:8400/app/#/firewall` live while sending actions.
