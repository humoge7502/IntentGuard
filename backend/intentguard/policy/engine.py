"""Policy engine (§69): deterministic, narrowing-only resolution.

Semantics (stated precisely so they are testable):
- A ``deny`` rule matching (tool, operation) blocks the action outright.
  Wildcards: rule.tool/operation of None or "*" match anything.
- A ``limit`` rule caps financial exposure for matching actions per currency;
  the effective cap is the MINIMUM across all matching rules and layers.
- There are no permissive rules. Policy can only narrow a capability; a more
  permissive layer can never widen a stricter one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from intentguard.core.enums import PolicyLayer
from intentguard.core.schemas import PolicyRule

_LAYER_ORDER = {
    PolicyLayer.ORGANIZATION: 0,
    PolicyLayer.USER: 1,
    PolicyLayer.AGENT: 2,
    PolicyLayer.INTENT: 3,
}


@dataclass
class PolicyOutcome:
    denied_by: PolicyRule | None = None
    caps: dict[str, Decimal] = field(default_factory=dict)
    matched_rules: list[PolicyRule] = field(default_factory=list)


class PolicyEngine:
    @staticmethod
    def _matches(rule: PolicyRule, tool: str, operation: str) -> bool:
        tool_ok = rule.tool is None or rule.tool in ("*", tool)
        op_ok = rule.operation is None or rule.operation in ("*", operation)
        return tool_ok and op_ok

    def evaluate(
        self, rules: list[PolicyRule], tool: str, operation: str
    ) -> PolicyOutcome:
        outcome = PolicyOutcome()
        deny_candidates: list[PolicyRule] = []
        for rule in rules:
            if not self._matches(rule, tool, operation):
                continue
            outcome.matched_rules.append(rule)
            if rule.effect == "deny":
                deny_candidates.append(rule)
            elif rule.effect == "limit" and rule.max_amount is not None:
                existing = outcome.caps.get(rule.currency)
                outcome.caps[rule.currency] = (
                    rule.max_amount if existing is None else min(existing, rule.max_amount)
                )
        if deny_candidates:
            deny_candidates.sort(key=lambda r: _LAYER_ORDER[r.layer])
            outcome.denied_by = deny_candidates[0]
        return outcome
