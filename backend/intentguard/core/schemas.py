"""Typed domain models. Every model forbids extra fields — data entering from
agents, tools, or HTTP is validated at the boundary (§66)."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from intentguard.core.enums import (
    ApprovalStatus,
    CapabilityStatus,
    CheckStatus,
    Decision,
    PolicyLayer,
    RiskBand,
    SideEffectClass,
)
from intentguard.core.ids import new_id


def utcnow() -> datetime:
    return datetime.now(UTC)


class IGBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# --------------------------------------------------------------------------
# Constraints — the vocabulary in which intent, capability scopes, and
# policies are expressed. Discriminated union keeps wire format explicit.
# --------------------------------------------------------------------------


class AmountLimit(IGBaseModel):
    kind: Literal["amount_limit"] = "amount_limit"
    currency: str = "INR"
    max_amount: Decimal


class BrandAllow(IGBaseModel):
    kind: Literal["brand_allow"] = "brand_allow"
    allowed: list[str]


class DestinationAllow(IGBaseModel):
    kind: Literal["destination_allow"] = "destination_allow"
    allowed: list[str]


class QuantityMax(IGBaseModel):
    kind: Literal["quantity_max"] = "quantity_max"
    max_quantity: int
    item: str | None = None


class TimeWindow(IGBaseModel):
    kind: Literal["time_window"] = "time_window"
    not_before: datetime | None = None
    not_after: datetime | None = None


class DataAccessScope(IGBaseModel):
    kind: Literal["data_access"] = "data_access"
    scopes: list[str]


class ApprovalRequirement(IGBaseModel):
    kind: Literal["approval_required"] = "approval_required"
    operations: list[str]
    above_amount: Decimal | None = None


Constraint = Annotated[
    AmountLimit | BrandAllow | DestinationAllow | QuantityMax | TimeWindow | DataAccessScope | ApprovalRequirement,
    Field(discriminator="kind"),
]


# --------------------------------------------------------------------------
# Identity
# --------------------------------------------------------------------------


class Organization(IGBaseModel):
    """Tenant boundary. Every tenant-owned object carries org_id (§36)."""

    org_id: str = Field(default_factory=lambda: new_id("org"))
    name: str
    created_at: datetime = Field(default_factory=utcnow)


class Principal(IGBaseModel):
    """A human or service accountable for agents and intents."""

    principal_id: str = Field(default_factory=lambda: new_id("usr"))
    org_id: str
    display_name: str
    kind: Literal["human", "service"] = "human"
    created_at: datetime = Field(default_factory=utcnow)


class AgentIdentity(IGBaseModel):
    """Identity of an autonomous agent. Attribution target for every action."""

    agent_id: str = Field(default_factory=lambda: new_id("agt"))
    org_id: str
    name: str
    owner_principal_id: str
    framework: str = "custom"
    # Reserved for the future reputation system (§16). NEVER security-authoritative:
    # the firewall never widens authorization based on trust_score.
    trust_score: float = 0.5
    created_at: datetime = Field(default_factory=utcnow)


class AgentSession(IGBaseModel):
    """A bounded run of an agent under exactly one intent and one capability."""

    session_id: str = Field(default_factory=lambda: new_id("ses"))
    org_id: str
    agent_id: str
    intent_id: str
    capability_id: str
    status: Literal["active", "closed"] = "active"
    # Trajectory defense: set when cumulative risk degrades the session; then
    # high-impact operations require human approval even if otherwise in scope.
    degraded: bool = False
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Intent
# --------------------------------------------------------------------------


class Ambiguity(IGBaseModel):
    field: str
    message: str
    severity: Literal["low", "medium", "high"] = "medium"


class IntentSpec(IGBaseModel):
    """Compiled human intent (§4). Versioned; decisions reference the version
    they were made against (§70)."""

    intent_id: str = Field(default_factory=lambda: new_id("int"))
    org_id: str
    principal_id: str
    version: int = 1
    goal: str
    raw_text: str
    constraints: list[Constraint] = Field(default_factory=list)
    allowed_operations: list[str] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)
    compiled_by: str = "rule_based_v1"
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------


class PolicyRule(IGBaseModel):
    """A single organization/user/agent/intent-layer rule.

    Two effects, both *narrowing* only:
    - ``deny``: any action matching tool/operation is blocked outright.
    - ``limit``: caps the financial exposure of matching actions; the effective
      cap is the minimum across all matching layers.
    There are no permissive rules — policy can only narrow what the capability
    grants, never widen it (§69).
    """

    rule_id: str = Field(default_factory=lambda: new_id("pol"))
    org_id: str
    layer: PolicyLayer
    name: str
    effect: Literal["deny", "limit"]
    tool: str | None = None
    operation: str | None = None
    max_amount: Decimal | None = None
    currency: str = "INR"
    reason_code: str = "POLICY_DENY"
    description: str = ""
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Capabilities
# --------------------------------------------------------------------------


class CapabilityScope(IGBaseModel):
    tool: str
    operations: list[str]
    param_constraints: list[Constraint] = Field(default_factory=list)


class Capability(IGBaseModel):
    """Least-privilege grant derived from intent ∩ policy (§5 Agent 5)."""

    capability_id: str = Field(default_factory=lambda: new_id("cap"))
    org_id: str
    intent_id: str
    agent_id: str
    version: int = 1
    status: CapabilityStatus = CapabilityStatus.ACTIVE
    scopes: list[CapabilityScope] = Field(default_factory=list)
    budget: AmountLimit | None = None
    expires_at: datetime | None = None
    revoked_reason: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Actions, context, observations
# --------------------------------------------------------------------------


class Observation(IGBaseModel):
    """Structured summary of external content an agent has read.

    Produced by trusted tool adapters (never by the agent itself) when reads
    execute through IntentGuard. Used for taint analysis and trajectory rules.
    """

    source_type: Literal["webpage", "document", "tool_output", "agent_message"]
    uri: str = ""
    content_digest: str = ""
    extracted_amounts: list[dict[str, str]] = Field(default_factory=list)
    extracted_brands: list[str] = Field(default_factory=list)
    extracted_destinations: list[str] = Field(default_factory=list)
    contains_credential_language: bool = False
    contains_instruction_language: bool = False
    contains_identity_claims: bool = False
    snippet: str = ""


class ActionProposal(IGBaseModel):
    """A proposed action awaiting authorization. Side effect has NOT occurred."""

    action_id: str = Field(default_factory=lambda: new_id("act"))
    org_id: str
    session_id: str
    agent_id: str
    tool: str
    operation: str
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    # Recent observations supplied by the trusted runtime, if any. The firewall
    # additionally merges observations recorded during this session.
    context: list[Observation] = Field(default_factory=list)
    requested_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Decisions
# --------------------------------------------------------------------------


class CheckResult(IGBaseModel):
    check: str
    status: CheckStatus
    detail: str = ""


class RiskSignal(IGBaseModel):
    code: str
    weight: int
    detail: str = ""


class RiskAssessment(IGBaseModel):
    score: int = Field(ge=0, le=100)
    band: RiskBand
    categories: list[str] = Field(default_factory=list)
    signals: list[RiskSignal] = Field(default_factory=list)


class DecisionRecord(IGBaseModel):
    """Explainable, auditable, replayable verdict (§72).

    Named DecisionRecord to avoid shadowing the core.enums.Decision verdict
    enum under Pydantic's deferred annotation resolution.
    """

    decision_id: str = Field(default_factory=lambda: new_id("dec"))
    org_id: str
    action_id: str
    action_digest: str
    session_id: str
    agent_id: str
    intent_id: str
    capability_id: str
    decision: Decision
    reasons: list[str] = Field(default_factory=list)
    checks: list[CheckResult] = Field(default_factory=list)
    risk: RiskAssessment
    versions: dict[str, Any] = Field(default_factory=dict)
    approval_id: str | None = None
    latency_ms: float = 0.0
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# Approvals
# --------------------------------------------------------------------------


class ApprovalRequest(IGBaseModel):
    """Human approval bound to ONE exact action digest (§8).

    Non-transferable and single-use: granting authorizes that digest only, and
    consuming it marks the request CONSUMED so it can never be reused.
    """

    approval_id: str = Field(default_factory=lambda: new_id("apr"))
    org_id: str
    session_id: str
    intent_id: str
    action_digest: str
    action_summary: dict[str, Any] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING
    granted_by: str | None = None
    requested_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime
    resolved_at: datetime | None = None


# --------------------------------------------------------------------------
# Audit & trajectory
# --------------------------------------------------------------------------


class AuditEvent(IGBaseModel):
    """Tamper-evident record. ``hash = SHA-256(prev_hash | seq | ts | payload)``."""

    seq: int
    org_id: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    hash: str
    signature: str | None = None
    created_at: datetime = Field(default_factory=utcnow)


class TrajectoryStep(IGBaseModel):
    org_id: str
    seq: int
    session_id: str
    action_id: str
    tool: str
    operation: str
    side_effect_class: SideEffectClass
    decision: Decision
    reasons: list[str] = Field(default_factory=list)
    risk_score: int
    taint: bool = False
    created_at: datetime = Field(default_factory=utcnow)


# --------------------------------------------------------------------------
# API keys
# --------------------------------------------------------------------------


class ApiKeyRecord(IGBaseModel):
    """API key metadata. Only the hash is stored; plaintext is shown once."""

    key_id: str = Field(default_factory=lambda: new_id("key"))
    org_id: str
    principal_id: str
    role: Literal["admin", "agent", "viewer"]
    key_hash: str
    name: str = ""
    revoked: bool = False
    created_at: datetime = Field(default_factory=utcnow)



