"""Capability minting (§5 Agent 5): intent ∩ policy → least-privilege grant.

Capabilities are the enforcement artifact the firewall checks against; they
are versioned, scoped per tool, revocable, optionally time-bounded, and carry
the budget derived from the intent. The agent never receives unrestricted
tool access — only the operations named by the intent, on the tools that
serve them.
"""
from __future__ import annotations

from datetime import timedelta

from intentguard.core.enums import CapabilityStatus
from intentguard.core.errors import ValidationError
from intentguard.core.schemas import (
    AmountLimit,
    BrandAllow,
    Capability,
    CapabilityScope,
    DestinationAllow,
    IntentSpec,
    QuantityMax,
    utcnow,
)
from intentguard.tools.base import ToolRegistry


class CapabilityManager:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def mint(
        self,
        intent: IntentSpec,
        agent_id: str,
        *,
        ttl_seconds: int | None = None,
        version: int = 1,
    ) -> Capability:
        if not intent.allowed_operations:
            raise ValidationError(
                "intent authorizes no operations; refusing to mint a capability"
            )
        scopes: dict[str, CapabilityScope] = {}
        for operation in intent.allowed_operations:
            tool_name = self._registry.tool_for_operation(operation)
            if tool_name is None:
                continue  # operation not served by any registered tool
            scope = scopes.get(tool_name)
            if scope is None:
                scope = CapabilityScope(tool=tool_name, operations=[])
                scopes[tool_name] = scope
            scope.operations.append(operation)

        # Attach entity constraints only to scopes whose tools consume them.
        tool_param_semantics: dict[str, set[str]] = {}
        for tool_name in scopes:
            adapter = self._registry.get(tool_name)
            if adapter is not None:
                tool_param_semantics[tool_name] = set(adapter.param_map.keys())
        for constraint in intent.constraints:
            if constraint.kind == "brand_allow" or constraint.kind == "destination_allow" or constraint.kind == "quantity_max":
                semantic = {
                    "brand_allow": "brand",
                    "destination_allow": "destination",
                    "quantity_max": "quantity",
                }[constraint.kind]
                for tool_name, semantics in tool_param_semantics.items():
                    if semantic in semantics:
                        scopes[tool_name].param_constraints.append(constraint)  # type: ignore[arg-type]

        budget = next(
            (c for c in intent.constraints if c.kind == "amount_limit"),
            None,
        )
        expires_at = (
            utcnow() + timedelta(seconds=ttl_seconds) if ttl_seconds is not None else None
        )
        return Capability(
            org_id=intent.org_id,
            intent_id=intent.intent_id,
            agent_id=agent_id,
            version=version,
            status=CapabilityStatus.ACTIVE,
            scopes=list(scopes.values()),
            budget=budget,  # type: ignore[arg-type]
            expires_at=expires_at,
        )
