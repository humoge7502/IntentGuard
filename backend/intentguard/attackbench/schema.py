"""AttackBench schema (§9–10). A scenario is a full sandbox setup: intent,
optional policy rules, agent(s), and an ordered action script. Benign
scenarios must run clean (any block = false positive); attack scenarios must
be stopped (final block or escalate = detected; allowed = miss)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Step:
    tool: str
    operation: str
    params: dict
    title: str = ""
    # execute when allowed — needed so reads record observations for taint
    execute: bool = True


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    family: str
    description: str
    steps: tuple[Step, ...]
    expect: str  # "allow_all" | "detected" | "block" | "escalate"
    benign: bool
    intent_text: str | None = None
    # direct intent spec override: {"goal", "raw_text", "allowed_operations", "constraints"}
    intent_spec: dict | None = None
    policy_rules: tuple[dict, ...] = ()
    setup: str = ""  # extra setup instruction for the runner, e.g. "expire_capability"
    tags: tuple[str, ...] = ()


@dataclass
class StepResult:
    seq: int
    title: str
    decision: str
    reasons: list[str]
    risk_score: int


@dataclass
class ScenarioResult:
    scenario_id: str
    family: str
    benign: bool
    passed: bool
    expected: str
    final_decision: str
    steps: list[StepResult] = field(default_factory=list)
    failure_reason: str = ""
    latencies_ms: list[float] = field(default_factory=list)


@dataclass
class BenchmarkReport:
    total: int
    attacks: int
    benign: int
    true_positives: int
    false_negatives: int
    true_negatives: int
    false_positives: int
    false_positive_escalations: int
    detection_rate: float
    false_positive_rate: float
    escalation_rate: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    per_family: dict
    failures: list[dict]

    def to_dict(self) -> dict:
        return self.__dict__.copy()
