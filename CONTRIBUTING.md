# Contributing

## Ground rules

1. **Security invariants are non-negotiable.** If a change could weaken any
   invariant in docs/SECURITY_MODEL.md §1 (independent enforcement, intent-
   derived authorization, uncertainty escalates, narrowing-only policy,
   tenant isolation, tamper-evident audit), it needs an explicit security
   review in the PR description.
2. **No fake completions.** Features are done when tests prove them. Mocks
   are labeled MOCK. Benchmark numbers come from real runs only.
3. **Never weaken a test to make it pass.** Security tests
   (test_firewall, test_trajectory, test_tenant_isolation, test_audit,
   test_attackbench) are regression floors.

## Workflow

```bash
# branch, implement, then:
cd backend
.venv/Scripts/python -m ruff check intentguard tests scripts
.venv/Scripts/python -m pytest tests/
```

- Conventional commits (`feat:`, `fix:`, `docs:`, `bench:`, `security:`).
- PRs must keep CI green (lint, full suite, AttackBench gate ≥95% detection /
  ≤2% FP, latency smoke).
- New attack families that demonstrate a bypass: land the fix first, then the
  family (so main never has a known-broken detection).

## Code style

- Strict typing, Pydantic models with `extra="forbid"` at boundaries.
- Reason codes/enums are stable wire identifiers.
- Comments only for constraints the code cannot express.
- Docs live in `docs/`; update DECISION_LOG.md for significant choices.

## Reporting bugs

GitHub issues; security issues via SECURITY.md. Include the decision record
(`checks` + `reasons`) for firewall misbehavior — it makes debugging fast.
