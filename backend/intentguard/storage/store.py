"""Persistence boundary. The engine depends on this protocol only; SQL is the
reference implementation, keeping the security core storage-agnostic and tests
fast (in-memory SQLite)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from intentguard.core.enums import ApprovalStatus
from intentguard.core.schemas import (
    AgentIdentity,
    AgentSession,
    ApiKeyRecord,
    ApprovalRequest,
    AuditEvent,
    Capability,
    DecisionRecord,
    IntentSpec,
    Observation,
    Organization,
    PolicyRule,
    Principal,
    TrajectoryStep,
)


class IntentGuardStore(ABC):
    """All methods are org-scoped where ownership applies (§36). Cross-org
    lookups must behave as not-found."""

    # --- organizations ----------------------------------------------------
    @abstractmethod
    def save_organization(self, org: Organization) -> None: ...

    @abstractmethod
    def get_organization(self, org_id: str) -> Organization | None: ...

    @abstractmethod
    def list_organizations(self) -> list[Organization]: ...

    # --- principals & agents ----------------------------------------------
    @abstractmethod
    def save_principal(self, principal: Principal) -> None: ...

    @abstractmethod
    def get_principal(self, org_id: str, principal_id: str) -> Principal | None: ...

    @abstractmethod
    def save_agent(self, agent: AgentIdentity) -> None: ...

    @abstractmethod
    def get_agent(self, org_id: str, agent_id: str) -> AgentIdentity | None: ...

    @abstractmethod
    def list_agents(self, org_id: str) -> list[AgentIdentity]: ...

    # --- api keys -----------------------------------------------------------
    @abstractmethod
    def save_api_key(self, record: ApiKeyRecord) -> None: ...

    @abstractmethod
    def get_api_key_by_hash(self, key_hash: str) -> ApiKeyRecord | None: ...

    @abstractmethod
    def list_api_keys(self, org_id: str) -> list[ApiKeyRecord]: ...

    # --- intents ------------------------------------------------------------
    @abstractmethod
    def save_intent(self, intent: IntentSpec) -> None: ...

    @abstractmethod
    def get_intent(self, org_id: str, intent_id: str) -> IntentSpec | None: ...

    @abstractmethod
    def list_intents(self, org_id: str) -> list[IntentSpec]: ...

    # --- capabilities --------------------------------------------------------
    @abstractmethod
    def save_capability(self, capability: Capability) -> None: ...

    @abstractmethod
    def get_capability(self, org_id: str, capability_id: str) -> Capability | None: ...

    @abstractmethod
    def list_capabilities(self, org_id: str) -> list[Capability]: ...

    # --- sessions -------------------------------------------------------------
    @abstractmethod
    def save_session(self, session: AgentSession) -> None: ...

    @abstractmethod
    def get_session(self, org_id: str, session_id: str) -> AgentSession | None: ...

    @abstractmethod
    def list_sessions(self, org_id: str) -> list[AgentSession]: ...

    # --- policy -----------------------------------------------------------------
    @abstractmethod
    def save_policy_rule(self, rule: PolicyRule) -> None: ...

    @abstractmethod
    def list_policy_rules(self, org_id: str) -> list[PolicyRule]: ...

    @abstractmethod
    def delete_policy_rule(self, org_id: str, rule_id: str) -> bool: ...

    # --- decisions -----------------------------------------------------------------
    @abstractmethod
    def save_decision(self, decision: DecisionRecord) -> None: ...

    @abstractmethod
    def get_decision(self, org_id: str, decision_id: str) -> DecisionRecord | None: ...

    @abstractmethod
    def list_decisions(
        self, org_id: str, session_id: str | None = None, limit: int = 200
    ) -> list[DecisionRecord]: ...

    @abstractmethod
    def find_allowed_digest(self, org_id: str, session_id: str, action_digest: str) -> bool: ...

    # --- approvals ---------------------------------------------------------------------
    @abstractmethod
    def save_approval(self, approval: ApprovalRequest) -> None: ...

    @abstractmethod
    def get_approval(self, org_id: str, approval_id: str) -> ApprovalRequest | None: ...

    @abstractmethod
    def list_approvals(
        self, org_id: str, status: ApprovalStatus | None = None
    ) -> list[ApprovalRequest]: ...

    @abstractmethod
    def find_granted_for_digest(
        self, org_id: str, session_id: str, action_digest: str
    ) -> ApprovalRequest | None: ...

    @abstractmethod
    def find_pending_for_digest(
        self, org_id: str, session_id: str, action_digest: str
    ) -> ApprovalRequest | None: ...

    # --- trajectory ------------------------------------------------------------------------
    @abstractmethod
    def append_trajectory_step(self, step: TrajectoryStep) -> None: ...

    @abstractmethod
    def list_trajectory(self, org_id: str, session_id: str) -> list[TrajectoryStep]: ...

    # --- executions (idempotency of side effects + replay detection) ----------------------------
    @abstractmethod
    def record_execution(
        self, org_id: str, decision_id: str, action_digest: str, summary: dict
    ) -> None: ...

    @abstractmethod
    def get_execution(self, org_id: str, decision_id: str) -> dict | None: ...

    @abstractmethod
    def find_executed_digest(self, org_id: str, session_id: str, action_digest: str) -> bool: ...


    @abstractmethod
    def append_observation(self, org_id: str, session_id: str, observation: Observation) -> None: ...

    @abstractmethod
    def list_observations(self, org_id: str, session_id: str) -> list[Observation]: ...

    @abstractmethod
    def session_observation_count(self, org_id: str, session_id: str) -> int: ...

    # --- audit chain --------------------------------------------------------------------------
    @abstractmethod
    def append_audit_event(self, event: AuditEvent) -> None: ...

    @abstractmethod
    def get_audit_head(self, org_id: str) -> AuditEvent | None: ...

    @abstractmethod
    def list_audit_events(self, org_id: str, limit: int = 500) -> list[AuditEvent]: ...

    # --- metrics -------------------------------------------------------------------------------
    @abstractmethod
    def decision_counts(self, org_id: str) -> dict[str, int]: ...

    @abstractmethod
    def count(self, table: str, org_id: str) -> int: ...

    # --- lifecycle -------------------------------------------------------------------------------
    @abstractmethod
    def close(self) -> None: ...


class StoreError(Exception):
    pass


def require_found(value: Any, entity: str, entity_id: str) -> Any:
    if value is None:
        from intentguard.core.errors import NotFoundError

        raise NotFoundError(f"{entity} not found: {entity_id}")
    return value
