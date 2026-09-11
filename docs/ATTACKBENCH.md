# AttackBench

IntentGuard's adversarial evaluation framework. Every scenario runs in a
fresh, isolated tenant against the **real** firewall with deterministic mock
tools. Nothing touches the real network; nothing is a real purchase.

## Running

```bash
# inside backend/, with the venv active
python scripts/bench_firewall.py 2000     # latency benchmark (different)
python - <<'EOF'
from intentguard.engine import IntentGuardEngine
from intentguard.storage.sql import SqlStore
from intentguard.attackbench.runner import run_benchmark
import json
engine = IntentGuardEngine(SqlStore("sqlite://"))
print(json.dumps(run_benchmark(engine, "bench"), indent=2)[:2000])
EOF
```

Or from the dashboard: **AttackBench → Run benchmark** (admin key).

## Verified full run — 2026-09-12, this repository, Windows 11, Python 3.13

```
scenarios: 208   attacks: 177   benign: 31
detection_rate: 1.0        (177/177 attacks stopped)
false_positive_rate: 0.0   (31/31 benign allowed)
escalation_rate: 0.0128
latency: p50 5.5ms · p95 9.8ms · p99 13.6ms
```

All 23 families at 100% pass. Raw numbers in docs/BENCHMARKS.md.

## Honest interpretation (read this before quoting numbers)

These families **co-evolve with the engine**: each family targets a check the
firewall implements, so a high detection rate demonstrates the checks work as
designed under parameterized variation. It is **not** a claim that IntentGuard
blocks 100% of real-world attacks. Real adversaries attack the gaps between
checks, the constraint vocabulary, and the compiler's coverage — that is what
the red-team loop (mission §39-40) is for: every new bypass becomes a family
here, and CI enforces the floors so nothing silently regresses.

Family size note: scenarios are distinct, meaningful parameterizations
(brands × quantities × cities × prices × intents). We deliberately did not pad
to "thousands" by duplicating permutations that exercise identical code paths;
the generator architecture scales to thousands by widening grids if coverage
value justifies it.

## Families (23)

**Benign (false-positive measurement):**
`benign_purchase` · `benign_research` · `benign_email_send`

**Attacks:**
| Family | Simulates |
|---|---|
| `budget_exceeded` | transaction amount manipulation over budget |
| `brand_violation` | buying unauthorized brands |
| `destination_manipulation` | redirecting delivery to unauthorized cities |
| `quantity_manipulation` | inflating volumes past authorization |
| `currency_manipulation` | currency switch to dodge INR budget |
| `indirect_prompt_injection` | malicious webpage drives divergent purchase |
| `credential_harvest` | phishing content then messaging-channel reach |
| `data_exfiltration` | emailing internal data to external addresses |
| `tool_abuse` | tools/ops outside the capability scope |
| `agent_impersonation` | second agent acting on another's session |
| `cross_agent_capability` | capability minted for a different agent |
| `replay_attack` | re-executing an identical completed action |
| `parameter_tampering` | smuggled fields (admin_override, skip_checks, …) |
| `policy_bypass` | acting under an active org/user deny |
| `excessive_agency` | operations never authorized by the intent |
| `malicious_document` | document instructs unauthorized transfer |
| `a2a_manipulation` | peer-agent message claims authority, then divergence |
| `multi_step_trajectory` | the mission §6 seven-step sequence |
| `ambiguous_intent_escalation` | no-budget purchase must escalate, not allow |
| `expired_capability` | stale authorization replay |

Scenario expectations: `allow_all` (benign — any block/escalation is a false
positive), `detected` (final block or escalate), or `escalate`.

## Adding a family

1. Add a generator in `backend/intentguard/attackbench/families.py` returning
   `Scenario` objects (dataclass in `schema.py`) — intent text or a direct
   spec, optional policy rules, ordered steps, expectation, tags.
2. Register it in `FAMILIES`.
3. `pytest tests/test_attackbench.py` — the runner, metrics, dashboard, and CI
   gate pick it up automatically. If your family legitimately breaks the
   engine: congratulations, you found a bypass — file it, fix the engine, and
   the family becomes the regression test (mission §40).

## Design rules

- Attack steps never contain real instructions for real-world abuse — all
  content is sandbox seeding (`*.example`, pseudo-scheme URIs).
- Every scenario gets a fresh org, so state cannot leak between cases.
- Metrics are computed from actual runs (see metrics.py); failures are listed
  with per-step decisions, never hidden.
