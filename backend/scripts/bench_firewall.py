"""Firewall latency benchmark (§54): measures the real decision path.

Reports p50/p95/p99 for:
- engine-only decisions (in-memory SQLite persistence included)
- a mixed workload of allow/block/escalate decisions

Run:  python scripts/bench_firewall.py [N]
Results are printed; BENCHMARKS.md quotes the verified run output.
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intentguard.config import Settings  # noqa: E402
from intentguard.engine import IntentGuardEngine  # noqa: E402
from intentguard.storage.sql import SqlStore  # noqa: E402
from tests.conftest import INTENT_TEXT, PURCHASE_OK  # noqa: E402


def bench(n: int) -> dict:
    store = SqlStore("sqlite://")
    engine = IntentGuardEngine(store, settings=Settings(store_kind="memory"))
    org = engine.create_organization("Bench Org")
    principal = engine.create_principal(org.org_id, "Bench Owner")
    agent = engine.register_agent(org.org_id, principal.principal_id, "bench-agent")
    intent = engine.compile_intent(org.org_id, principal.principal_id, INTENT_TEXT)

    latencies: list[float] = []
    counts = {"allow": 0, "block": 0, "escalate": 0}
    benign_session = engine.start_session(org.org_id, agent.agent_id, intent.intent_id)
    attack_session = engine.start_session(org.org_id, agent.agent_id, intent.intent_id)
    benign_in_session = 0
    attack_in_session = 0
    for i in range(n):
        is_probe = i % 10 in (7, 9)
        if is_probe:
            # attack probes run in disposable sessions; two blocks would
            # (correctly) degrade a shared session and skew steady state
            if attack_in_session >= 3:
                attack_session = engine.start_session(org.org_id, agent.agent_id, intent.intent_id)
                attack_in_session = 0
            session = attack_session
            attack_in_session += 1
            if i % 10 == 7:
                params = {**PURCHASE_OK, "quantity": 500, "unit_price": "15000", "brand": "Apple"}
            else:
                params = {**PURCHASE_OK, "currency": "USD", "unit_price": "120"}
        else:
            if benign_in_session >= 40:
                benign_session = engine.start_session(org.org_id, agent.agent_id, intent.intent_id)
                benign_in_session = 0
            session = benign_session
            benign_in_session += 1
            params = {**PURCHASE_OK, "quantity": 1 + (i % 90)}
        decision = engine.propose(
            org.org_id, session.session_id, agent.agent_id,
            "shopping_api", "purchase", params,
        )
        counts[decision.decision.value] += 1
        latencies.append(decision.latency_ms)

    ordered = sorted(latencies)
    def pct(p: float) -> float:
        return round(ordered[min(len(ordered) - 1, round(p * (len(ordered) - 1)))], 3)

    return {
        "n": n,
        "mean_ms": round(statistics.mean(latencies), 3),
        "p50_ms": pct(0.50),
        "p95_ms": pct(0.95),
        "p99_ms": pct(0.99),
        "max_ms": round(max(latencies), 3),
        "decisions": counts,
    }


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    result = bench(n)
    print(f"firewall decision benchmark (n={result['n']})")
    for key, value in result.items():
        if key != "decisions":
            print(f"  {key:10s} {value}")
    print(f"  decisions  {result['decisions']}")
