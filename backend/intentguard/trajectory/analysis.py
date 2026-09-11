"""Trajectory analysis (§6): the sequence is the attack surface.

Individually-plausible actions can compose into an attack. This analyzer runs
deterministic rules over the session's accumulated steps and the session's
recorded observations, producing risk signals, hard reasons, and capability
degradation suggestions.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from intentguard.core.enums import HIGH_IMPACT_CLASSES
from intentguard.core.schemas import Observation, RiskSignal
from intentguard.storage.store import IntentGuardStore

# Tools whose operations are meaningful targets after credential-harvest content
CREDENTIAL_TARGET_TOOLS = frozenset({"banking_api", "email_api"})

DEFAULT_WEIGHTS = {
    "RETRY_AFTER_BLOCK": 20,
    "RAPID_HIGH_IMPACT": 15,
    "RISK_ACCUMULATION": 15,
}


@dataclass
class TrajectoryResult:
    signals: list[RiskSignal] = field(default_factory=list)
    hard_reasons: list[str] = field(default_factory=list)
    degrade: bool = False


class TrajectoryAnalyzer:
    def __init__(self, store: IntentGuardStore, weights: dict[str, int] | None = None) -> None:
        self._store = store
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    def _signal(self, code: str, detail: str) -> RiskSignal:
        return RiskSignal(code=code, weight=self.weights.get(code, 10), detail=detail)

    def analyze(
        self,
        org_id: str,
        session_id: str,
        action_digest: str,
        proposal_tool: str,
        observations: list[Observation],
    ) -> TrajectoryResult:
        result = TrajectoryResult()
        steps = self._store.list_trajectory(org_id, session_id)

        # Replay: this exact action was already executed in this session.
        if self._store.find_executed_digest(org_id, session_id, action_digest):
            result.hard_reasons.append("REPLAY_SUSPECTED")

        # Credential-harvest pattern: credential-phishing content was read,
        # and the agent now reaches for a credential-bearing or messaging tool.
        if proposal_tool in CREDENTIAL_TARGET_TOOLS and any(
            o.contains_credential_language for o in observations
        ):
            result.hard_reasons.append("TRAJECTORY_CREDENTIAL_HARVEST")

        blocked = [s for s in steps if s.decision.value == "block"]
        if len(blocked) >= 2:
            result.signals.append(
                self._signal("RETRY_AFTER_BLOCK", f"{len(blocked)} prior blocked attempts in this session")
            )

        high_impact_allowed = [
            s for s in steps
            if s.decision.value == "allow" and s.side_effect_class in HIGH_IMPACT_CLASSES
        ]
        if len(high_impact_allowed) >= 3:
            result.signals.append(
                self._signal("RAPID_HIGH_IMPACT", f"{len(high_impact_allowed)} high-impact actions already executed")
            )

        if steps:
            avg_risk = sum(s.risk_score for s in steps) / len(steps)
            if avg_risk >= 40:
                result.signals.append(
                    self._signal("RISK_ACCUMULATION", f"average trajectory risk {avg_risk:.0f}/100")
                )

        prior_elevated = [
            s for s in steps
            if s.decision.value == "allow" and s.risk_score >= 50
        ]
        if len(prior_elevated) >= 2 or len(blocked) >= 2:
            result.degrade = True

        return result
