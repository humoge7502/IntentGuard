"""Benchmark metrics. Computed from actual scenario runs — never fabricated."""
from __future__ import annotations

from intentguard.attackbench.schema import BenchmarkReport, ScenarioResult


def build_report(results: list[ScenarioResult], latencies_ms: list[float]) -> BenchmarkReport:
    attacks = [r for r in results if not r.benign]
    benign = [r for r in results if r.benign]

    tp = sum(1 for r in attacks if r.passed)
    fn = len(attacks) - tp
    tn = sum(1 for r in benign if r.passed)
    fp = len(benign) - tn

    fp_escalations = sum(
        1
        for r in benign
        if not r.passed and any(s.decision == "escalate" for s in r.steps)
    )
    escalations = sum(1 for r in results for s in r.steps if s.decision == "escalate")
    total_steps = sum(len(r.steps) for r in results)

    per_family: dict[str, dict] = {}
    for r in results:
        fam = per_family.setdefault(
            r.family,
            {"total": 0, "passed": 0, "blocked": 0, "escalated": 0, "allowed": 0},
        )
        fam["total"] += 1
        fam["passed"] += 1 if r.passed else 0
        if r.final_decision == "block":
            fam["blocked"] += 1
        elif r.final_decision == "escalate":
            fam["escalated"] += 1
        else:
            fam["allowed"] += 1

    sorted_lat = sorted(latencies_ms)
    def pct(p: float) -> float:
        if not sorted_lat:
            return 0.0
        idx = min(len(sorted_lat) - 1, max(0, round(p * (len(sorted_lat) - 1))))
        return round(sorted_lat[idx], 3)

    failures = [
        {
            "scenario_id": r.scenario_id,
            "family": r.family,
            "expected": r.expected,
            "final_decision": r.final_decision,
            "failure_reason": r.failure_reason,
            "steps": [s.__dict__ for s in r.steps],
        }
        for r in results
        if not r.passed
    ][:200]

    return BenchmarkReport(
        total=len(results),
        attacks=len(attacks),
        benign=len(benign),
        true_positives=tp,
        false_negatives=fn,
        true_negatives=tn,
        false_positives=fp,
        false_positive_escalations=fp_escalations,
        detection_rate=round(tp / len(attacks), 4) if attacks else 0.0,
        false_positive_rate=round(fp / len(benign), 4) if benign else 0.0,
        escalation_rate=round(escalations / total_steps, 4) if total_steps else 0.0,
        latency_p50_ms=pct(0.50),
        latency_p95_ms=pct(0.95),
        latency_p99_ms=pct(0.99),
        per_family=per_family,
        failures=failures,
    )
