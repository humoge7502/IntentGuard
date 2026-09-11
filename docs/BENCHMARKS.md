# Benchmarks

All numbers below are from real runs of this repository. Machine: Windows 11
x64, Python 3.13.5, in-memory SQLite persistence. Nothing here is projected,
extrapolated, or aspirational. Re-run everything with the quoted commands.

## 1. Firewall decision latency — 2026-09-12

Command: `python scripts/bench_firewall.py 2000` (mixed workload: 80% benign
purchase, 20% constraint-violation probes; sessions rotated to avoid
degradation dominating steady state; includes full persistence + audit).

```
n        2000
mean_ms  9.233
p50_ms   8.528
p95_ms   15.466
p99_ms   21.360
max_ms   91.806
decisions  {'allow': 1600, 'block': 400, 'escalate': 0}
```

Context: each decision performs identity, capability, tool/operation,
parameter, policy, intent-alignment, taint, and trajectory checks, writes a
decision row, appends a trajectory step, appends a hash-chained audit event,
and publishes to the event bus.

Engineering note: an earlier run measured p50 ≈ 75 ms. Root cause was a real
defect — the approval-dedupe path scanned all pending approvals per escalation
(O(n²) over accumulated requests). Fixed with a scoped indexed query
(`find_pending_for_digest`); the same fix is covered by behavior tests. This
is exactly why §54 of the mission says measure first.

## 2. AttackBench — 2026-09-12

Command: `intentguard.attackbench.runner.run_benchmark` (all families, no cap)
— same run is reproducible via the dashboard.

```
scenarios: 208 (177 attacks / 31 benign)
detection_rate:       1.0     (177/177)
false_positive_rate:  0.0     (31/31 benign allowed)
escalation_rate:      0.0128
latency: p50 5.5ms · p95 9.8ms · p99 13.6ms
per-family: all 23 families 100% pass
```

Interpretation and caveats: see the "Honest interpretation" section of
docs/ATTACKBENCH.md. Families co-evolve with the engine; this is a regression
floor, not a universal-safety claim.

## 3. Test suite — 2026-09-12

```
68 passed (unit, integration, security, tenant isolation, adversarial gate)
wall time ≈ 16-19 s
```

Command: `pytest tests/` inside `backend/`.

## 4. What is NOT benchmarked (honestly)

- Multi-user concurrent throughput (no load harness yet).
- PostgreSQL latency profile (SQLite measured; PG expected similar for this
  access pattern, unverified).
- Dashboard rendering performance on large histories.
- LLM-assisted compilation latency (no LLM in the loop by design).
- Long-horizon memory growth of the decision store (retention policy
  documented, automation not built).
