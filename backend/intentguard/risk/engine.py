"""Risk engine (§7): deterministic scoring over weighted signals.

Hard policy violations are NOT risk-scored decisions — they block regardless
of score. Risk scoring governs the uncertain middle: signals accumulate into
a 0-100 score with bands low/moderate/high/critical; high escalates to a
human, critical blocks. Weights are configurable per deployment.
"""
from __future__ import annotations

from intentguard.core.enums import RiskBand
from intentguard.core.schemas import RiskAssessment, RiskSignal

DEFAULT_WEIGHTS: dict[str, int] = {
    "EXTERNAL_TAINT": 30,
    "INSTRUCTION_TAINT": 25,
    "INTENT_DIVERGENCE": 25,
    "SUSPICIOUS_IDENTITY_CLAIM": 20,
    "RETRY_AFTER_BLOCK": 20,
    "RAPID_HIGH_IMPACT": 15,
    "RISK_ACCUMULATION": 15,
    "HIGH_IMPACT_UNSCOPED": 25,
    "EXTERNAL_READ_RECENT": 10,
}

_CODE_CATEGORY = {
    "EXTERNAL": "INTEGRITY",
    "INSTRUCTION": "INTEGRITY",
    "INTENT": "INTEGRITY",
    "SUSPICIOUS": "INTEGRITY",
    "RETRY": "TRAJECTORY",
    "RAPID": "TRAJECTORY",
    "RISK": "TRAJECTORY",
    "HIGH_IMPACT": "PRIVILEGE",
    "CREDENTIAL": "DATA_EXFIL",
    "EXFIL": "DATA_EXFIL",
}

_BAND_THRESHOLDS = ((75, RiskBand.CRITICAL), (50, RiskBand.HIGH), (25, RiskBand.MODERATE))


class RiskEngine:
    def __init__(self, weights: dict[str, int] | None = None) -> None:
        self.weights = {**DEFAULT_WEIGHTS, **(weights or {})}

    def signal(self, code: str, detail: str = "") -> RiskSignal:
        return RiskSignal(code=code, weight=self.weights.get(code, 10), detail=detail)

    def assess(self, signals: list[RiskSignal]) -> RiskAssessment:
        score = min(100, sum(s.weight for s in signals))
        band = RiskBand.LOW
        for threshold, candidate in _BAND_THRESHOLDS:
            if score >= threshold:
                band = candidate
                break
        categories: list[str] = []
        for signal in signals:
            category = next(
                (cat for prefix, cat in _CODE_CATEGORY.items() if signal.code.startswith(prefix)),
                "GENERAL",
            )
            if category not in categories:
                categories.append(category)
        return RiskAssessment(score=score, band=band, categories=categories, signals=signals)
