"""Tool adapter contract.

Tools are the ONLY code allowed to touch the outside world, and they execute
exclusively through the firewall (ALLOW decisions). Adapters declare the
semantics the firewall needs for deterministic constraint checking:
side-effect class, parameter shape, financial exposure, and entity facts.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from intentguard.core.enums import SideEffectClass
from intentguard.core.errors import ValidationError


@dataclass(frozen=True)
class OperationSpec:
    name: str
    side_effect_class: SideEffectClass
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    description: str = ""


@dataclass
class ExecutionContext:
    org_id: str
    session_id: str
    agent_id: str
    action_id: str


@dataclass
class ToolResult:
    ok: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    # Structured observation of external content, produced by trusted adapters
    # for read-style operations (webpage/document). Never agent-supplied.
    observation: dict[str, Any] | None = None


class ToolAdapter:
    """Base class for tool adapters.

    ``param_map`` maps semantic roles to parameter names so the firewall can
    check intent constraints generically: brand, destination, quantity,
    amount, currency, item.
    """

    name: str = "tool"
    description: str = ""
    specs: dict[str, OperationSpec] = {}
    param_map: dict[str, str] = {}

    def __init__(self) -> None:
        # Fault injection profile — configured by the TEST HARNESS only, never
        # by agent-controlled parameters (§11). Instance-level so harnesses
        # can vary it per adapter without leaking across tools.
        self.fault_profile: dict[str, Any] = {}

    def spec(self, operation: str) -> OperationSpec:
        try:
            return self.specs[operation]
        except KeyError:
            raise ValidationError(f"unknown operation '{operation}' for tool '{self.name}'") from None

    def side_effect_class(self, operation: str) -> SideEffectClass:
        return self.spec(operation).side_effect_class

    def validate_params(self, operation: str, params: dict[str, Any]) -> list[str]:
        """Structural validation. Returns human-readable error strings."""
        spec = self.spec(operation)
        errors: list[str] = []
        for name in spec.required:
            if name not in params or params[name] in (None, ""):
                errors.append(f"missing required parameter '{name}'")
        allowed = set(spec.required) | set(spec.optional)
        for name in params:
            if name not in allowed:
                errors.append(f"unexpected parameter '{name}'")
        return errors

    def financial_exposure(
        self, operation: str, params: dict[str, Any]
    ) -> tuple[Decimal, str] | None:
        """(amount, currency) at risk, or None for non-financial operations."""
        amount_key = self.param_map.get("amount")
        if amount_key is None or amount_key not in params:
            return None
        try:
            amount = Decimal(str(params[amount_key]))
        except Exception:
            return None
        quantity_key = self.param_map.get("quantity")
        if quantity_key and quantity_key in params:
            try:
                amount = amount * Decimal(str(params[quantity_key]))
            except Exception:
                return None
        currency_key = self.param_map.get("currency")
        currency = str(params.get(currency_key, "INR")) if currency_key else "INR"
        return amount, currency

    def entity_facts(self, operation: str, params: dict[str, Any]) -> dict[str, Any]:
        """Semantic entities the firewall checks against intent constraints."""
        facts: dict[str, Any] = {}
        for semantic in ("brand", "destination", "quantity", "item"):
            key = self.param_map.get(semantic)
            if key and key in params:
                facts[semantic] = params[key]
        currency_key = self.param_map.get("currency")
        if currency_key and currency_key in params:
            facts["currency"] = params[currency_key]
        return facts

    def execute(self, operation: str, params: dict[str, Any], ctx: ExecutionContext) -> ToolResult:
        raise NotImplementedError


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolAdapter] = {}
        self._op_tool: dict[str, str] = {}

    def register(self, adapter: ToolAdapter, override: bool = False) -> None:
        if adapter.name in self._tools and not override:
            raise ValidationError(f"tool '{adapter.name}' already registered")
        self._tools[adapter.name] = adapter
        for op_name in adapter.specs:
            if op_name in self._op_tool and not override:
                raise ValidationError(
                    f"operation '{op_name}' already registered to tool '{self._op_tool[op_name]}'"
                )
            self._op_tool[op_name] = adapter.name

    def get(self, name: str) -> ToolAdapter | None:
        return self._tools.get(name)

    def require(self, name: str) -> ToolAdapter:
        tool = self._tools.get(name)
        if tool is None:
            raise ValidationError(f"unknown tool '{name}'")
        return tool

    def tool_for_operation(self, operation: str) -> str | None:
        return self._op_tool.get(operation)

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "operations": [s.name for s in t.specs.values()],
                "side_effect_classes": {
                    s.name: s.side_effect_class.value for s in t.specs.values()
                },
            }
            for t in self._tools.values()
        ]

    def __contains__(self, name: str) -> bool:
        return name in self._tools
