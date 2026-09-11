"""Intent graph construction (§26): the UI-facing decomposition of an intent
into goal, constraints, capabilities, and approval requirements, with edges
that make authorization derivable at a glance."""
from __future__ import annotations

from typing import Any

from intentguard.core.schemas import Capability, IntentSpec


def build_intent_graph(
    intent: IntentSpec, capability: Capability | None = None
) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    def add(node: dict[str, Any], parent: str | None) -> str:
        nodes.append(node)
        node_id = str(node["id"])
        if parent:
            edges.append({"from": parent, "to": node_id})
        return node_id

    root = add(
        {"id": "goal", "type": "goal", "label": intent.goal, "detail": intent.raw_text[:200]},
        None,
    )

    for index, constraint in enumerate(intent.constraints):
        kind = constraint.kind
        if kind == "amount_limit":
            label = f"Budget ≤ {constraint.max_amount} {constraint.currency}"
            detail = "spending cap derived from the human's words"
        elif kind == "brand_allow":
            label = f"Brands: {', '.join(constraint.allowed)}"
            detail = "only these brands are authorized"
        elif kind == "destination_allow":
            label = f"Destinations: {', '.join(constraint.allowed)}"
            detail = "delivery/shipping restricted to these locations"
        elif kind == "quantity_max":
            label = f"Quantity ≤ {constraint.max_quantity}" + (f" {constraint.item}" if constraint.item else "")
            detail = "volume cap"
        elif kind == "time_window":
            label = "Time window"
            detail = f"not_after={constraint.not_after.isoformat() if constraint.not_after else '—'}"
        elif kind == "data_access":
            label = f"Data scopes: {', '.join(constraint.scopes)}"
            detail = "data-access boundary"
        elif kind == "approval_required":
            label = f"Approval required: {', '.join(constraint.operations)}"
            detail = "human must approve before execution"
        else:
            label = kind
            detail = ""
        add(
            {"id": f"constraint_{index}", "type": "constraint", "subtype": kind, "label": label, "detail": detail},
            root,
        )

    for index, op in enumerate(intent.allowed_operations):
        add(
            {"id": f"operation_{index}", "type": "operation", "label": op, "detail": "operation the agent may request"},
            root,
        )

    for index, amb in enumerate(intent.ambiguities):
        add(
            {
                "id": f"ambiguity_{index}",
                "type": "ambiguity",
                "label": amb.field,
                "detail": amb.message,
                "severity": amb.severity,
            },
            root,
        )

    if capability is not None:
        cap_node = add(
            {
                "id": "capability",
                "type": "capability",
                "label": f"capability {capability.capability_id[:14]}…",
                "detail": f"v{capability.version} · {capability.status.value}",
            },
            root,
        )
        for index, scope in enumerate(capability.scopes):
            add(
                {
                    "id": f"scope_{index}",
                    "type": "scope",
                    "label": f"{scope.tool}: {', '.join(scope.operations)}",
                    "detail": "least-privilege tool scope",
                },
                cap_node,
            )

    return {"nodes": nodes, "edges": edges}
