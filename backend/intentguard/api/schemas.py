"""Request bodies. ``extra="forbid"`` everywhere — unknown fields are rejected
rather than silently ignored (§66)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrictModel(BaseModel):
    model_config = {"extra": "forbid"}


class IntentCreate(StrictModel):
    text: str = Field(min_length=4, max_length=4000)


class AgentCreate(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    framework: str = Field(default="custom", max_length=60)


class SessionCreate(StrictModel):
    agent_id: str
    intent_id: str
    ttl_seconds: int | None = Field(default=None, ge=1, le=60 * 60 * 24 * 30)


class EvaluateRequest(StrictModel):
    session_id: str
    agent_id: str
    tool: str
    operation: str
    params: dict[str, Any] = Field(default_factory=dict)
    context: list[dict[str, Any]] = Field(default_factory=list)


class ExecuteRequest(StrictModel):
    decision_id: str


class ApprovalAction(StrictModel):
    approver: str = Field(min_length=1, max_length=120)


class RevokeRequest(StrictModel):
    reason: str = Field(min_length=1, max_length=500)


class PolicyRuleCreate(StrictModel):
    layer: str = Field(pattern="^(organization|user|agent|intent)$")
    name: str = Field(min_length=1, max_length=120)
    effect: str = Field(pattern="^(deny|limit)$")
    tool: str | None = None
    operation: str | None = None
    max_amount: str | float | None = None
    currency: str = "INR"
    reason_code: str = "POLICY_DENY"
    description: str = ""


class BenchmarkRun(StrictModel):
    max_per_family: int = Field(default=40, ge=1, le=500)
