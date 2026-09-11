"""Engine facade — one object wiring the whole control plane.

Lifecycle: create org → principal → agent → compile intent → start session
(mints the capability) → evaluate actions through the firewall → execute only
ALLOWed decisions through the trusted tool adapter → approvals/revocation/
audit/trajectory inspection.
"""
from __future__ import annotations

from typing import Any

from intentguard.approvals.service import ApprovalService
from intentguard.audit.chain import AuditChain
from intentguard.capabilities.manager import CapabilityManager
from intentguard.config import Settings
from intentguard.core.enums import Decision
from intentguard.core.errors import ConflictError, NotFoundError, ValidationError
from intentguard.core.schemas import (
    ActionProposal,
    AgentIdentity,
    AgentSession,
    ApiKeyRecord,
    Observation,
    Organization,
    PolicyRule,
    Principal,
)
from intentguard.firewall.bus import EventBus
from intentguard.firewall.pipeline import EXTERNAL_CONTENT_TOOLS, ActionFirewall
from intentguard.intents.compiler import RuleBasedIntentCompiler
from intentguard.intents.graph import build_intent_graph
from intentguard.policy.engine import PolicyEngine
from intentguard.risk.engine import RiskEngine
from intentguard.storage.store import IntentGuardStore
from intentguard.tools.base import ExecutionContext, ToolRegistry, ToolResult
from intentguard.tools import default_registry
from intentguard.trajectory.analysis import TrajectoryAnalyzer

import hashlib
import secrets


class IntentGuardEngine:
    def __init__(
        self,
        store: IntentGuardStore,
        registry: ToolRegistry | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.store = store
        self.registry = registry or default_registry()
        self.settings = settings or Settings()
        self.events = EventBus()
        self.audit = AuditChain(store, self.settings.audit_signing_key)
        self.policy = PolicyEngine()
        self.risk = RiskEngine()
        self.trajectory = TrajectoryAnalyzer(store)
        self.approvals = ApprovalService(store, self.audit)
        self.capabilities = CapabilityManager(self.registry)
        self.compiler = RuleBasedIntentCompiler()
        self.firewall = ActionFirewall(
            store=store,
            registry=self.registry,
            policy_engine=self.policy,
            risk_engine=self.risk,
            trajectory_analyzer=self.trajectory,
            approvals=self.approvals,
            audit=self.audit,
            events=self.events,
        )

    # ------------------------------------------------------------------ #
    # Organizations, principals, agents                                   #
    # ------------------------------------------------------------------ #

    def create_organization(self, name: str) -> Organization:
        org = Organization(name=name)
        self.store.save_organization(org)
        self.audit.append(org.org_id, "organization.created", {"name": name})
        return org

    def create_principal(self, org_id: str, display_name: str, kind: str = "human") -> Principal:
        principal = Principal(org_id=org_id, display_name=display_name, kind=kind)  # type: ignore[arg-type]
        self.store.save_principal(principal)
        return principal

    def register_agent(
        self, org_id: str, owner_principal_id: str, name: str, framework: str = "custom"
    ) -> AgentIdentity:
        agent = AgentIdentity(
            org_id=org_id, owner_principal_id=owner_principal_id, name=name, framework=framework
        )
        self.store.save_agent(agent)
        self.audit.append(org_id, "agent.registered", {"agent_id": agent.agent_id, "name": name})
        return agent

    # ------------------------------------------------------------------ #
    # API keys                                                            #
    # ------------------------------------------------------------------ #

    def create_api_key(self, org_id: str, principal_id: str, role: str, name: str = "") -> tuple[ApiKeyRecord, str]:
        if role not in {"admin", "agent", "viewer"}:
            raise ValidationError("role must be admin|agent|viewer")
        plaintext = "ig_" + secrets.token_urlsafe(32)
        key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        record = ApiKeyRecord(org_id=org_id, principal_id=principal_id, role=role, key_hash=key_hash, name=name)  # type: ignore[arg-type]
        self.store.save_api_key(record)
        self.audit.append(org_id, "apikey.created", {"key_id": record.key_id, "role": role})
        return record, plaintext

    # ------------------------------------------------------------------ #
    # Intents & capabilities                                              #
    # ------------------------------------------------------------------ #

    def compile_intent(self, org_id: str, principal_id: str, text: str) -> Any:
        intent = self.compiler.compile(org_id, principal_id, text)
        self.store.save_intent(intent)
        self.audit.append(
            org_id,
            "intent.created",
            {"intent_id": intent.intent_id, "goal": intent.goal, "version": intent.version},
        )
        return intent

    def intent_graph(self, org_id: str, intent_id: str) -> dict[str, Any]:
        intent = self.store.get_intent(org_id, intent_id)
        if intent is None:
            raise NotFoundError(f"intent not found: {intent_id}")
        capabilities = [
            c for c in self.store.list_capabilities(org_id) if c.intent_id == intent_id
        ]
        return build_intent_graph(intent, capabilities[0] if capabilities else None)

    def mint_capability(self, org_id: str, intent_id: str, agent_id: str, ttl_seconds: int | None = None):
        intent = self.store.get_intent(org_id, intent_id)
        if intent is None:
            raise NotFoundError(f"intent not found: {intent_id}")
        agent = self.store.get_agent(org_id, agent_id)
        if agent is None:
            raise NotFoundError(f"agent not found: {agent_id}")
        capability = self.capabilities.mint(intent, agent_id, ttl_seconds=ttl_seconds)
        self.store.save_capability(capability)
        self.audit.append(
            org_id,
            "capability.minted",
            {"capability_id": capability.capability_id, "intent_id": intent_id, "agent_id": agent_id},
        )
        return capability

    def revoke_capability(self, org_id: str, capability_id: str, reason: str):
        capability = self.store.get_capability(org_id, capability_id)
        if capability is None:
            raise NotFoundError(f"capability not found: {capability_id}")
        from intentguard.core.enums import CapabilityStatus

        capability.status = CapabilityStatus.REVOKED
        capability.revoked_reason = reason
        self.store.save_capability(capability)
        self.audit.append(
            org_id,
            "capability.revoked",
            {"capability_id": capability_id, "reason": reason},
        )
        return capability

    # ------------------------------------------------------------------ #
    # Sessions                                                            #
    # ------------------------------------------------------------------ #

    def start_session(self, org_id: str, agent_id: str, intent_id: str, ttl_seconds: int | None = None) -> AgentSession:
        agent = self.store.get_agent(org_id, agent_id)
        if agent is None:
            raise NotFoundError(f"agent not found: {agent_id}")
        capability = self.mint_capability(org_id, intent_id, agent_id, ttl_seconds=ttl_seconds)
        session = AgentSession(
            org_id=org_id, agent_id=agent_id, intent_id=intent_id, capability_id=capability.capability_id
        )
        self.store.save_session(session)
        self.audit.append(
            org_id,
            "session.started",
            {"session_id": session.session_id, "agent_id": agent_id, "intent_id": intent_id},
        )
        return session

    # ------------------------------------------------------------------ #
    # Firewall                                                            #
    # ------------------------------------------------------------------ #

    def propose(
        self,
        org_id: str,
        session_id: str,
        agent_id: str,
        tool: str,
        operation: str,
        params: dict[str, Any] | None = None,
        context: list[Observation] | None = None,
    ) -> Any:
        proposal = ActionProposal(
            org_id=org_id,
            session_id=session_id,
            agent_id=agent_id,
            tool=tool,
            operation=operation,
            params=params or {},
            context=context or [],
        )
        return self.firewall.evaluate(proposal)

    def execute(self, org_id: str, decision_id: str) -> ToolResult:
        """Execute an ALLOWed decision through the trusted tool adapter.

        Execution is idempotent per decision: a decision can drive at most one
        side effect, ever.
        """
        decision = self.store.get_decision(org_id, decision_id)
        if decision is None:
            raise NotFoundError(f"decision not found: {decision_id}")
        if decision.decision != Decision.ALLOW:
            raise ConflictError(
                f"decision is {decision.decision.value}; only ALLOW decisions may execute"
            )
        if self.store.get_execution(org_id, decision_id) is not None:
            raise ConflictError("decision already executed")

        tool = self.registry.require(self._tool_of(decision))
        session = self.store.get_session(org_id, decision.session_id)
        ctx = ExecutionContext(
            org_id=org_id,
            session_id=decision.session_id,
            agent_id=decision.agent_id,
            action_id=decision.action_id,
        )
        params = self._params_of(decision)
        result = tool.execute(
            self._operation_of(decision), params, ctx
        )
        self.store.record_execution(
            org_id,
            decision_id,
            decision.action_digest,
            {
                "tool": tool.name,
                "operation": self._operation_of(decision),
                "ok": result.ok,
                "error": result.error,
                "session_id": decision.session_id,
                "agent_id": decision.agent_id,
            },
        )
        self.audit.append(
            org_id,
            "action.executed",
            {
                "decision_id": decision_id,
                "tool": tool.name,
                "operation": self._operation_of(decision),
                "ok": result.ok,
            },
        )
        if result.observation is not None and session is not None:
            self.store.append_observation(
                org_id, decision.session_id, Observation.model_validate(result.observation)
            )
        self.events.publish(
            {"type": "execution", "execution": {"decision_id": decision_id, "ok": result.ok}}
        )
        return result

    # decision params/tool/operation are reconstructed from the stored decision
    # summary captured at proposal time.
    DECISION_META_KEY = "proposal"

    def _tool_of(self, decision: Any) -> str:
        meta = decision.versions.get(self.DECISION_META_KEY, {})
        return str(meta.get("tool", ""))

    def _operation_of(self, decision: Any) -> str:
        meta = decision.versions.get(self.DECISION_META_KEY, {})
        return str(meta.get("operation", ""))

    def _params_of(self, decision: Any) -> dict[str, Any]:
        meta = decision.versions.get(self.DECISION_META_KEY, {})
        return dict(meta.get("params", {}))

    # ------------------------------------------------------------------ #
    # Approvals                                                           #
    # ------------------------------------------------------------------ #

    def grant_approval(self, org_id: str, approval_id: str, approver: str):
        approval = self.approvals.grant(org_id, approval_id, approver)
        self.events.publish(
            {"type": "approval", "approval": approval.model_dump(mode="json")}
        )
        return approval

    def deny_approval(self, org_id: str, approval_id: str, approver: str):
        approval = self.approvals.deny(org_id, approval_id, approver)
        self.events.publish(
            {"type": "approval", "approval": approval.model_dump(mode="json")}
        )
        return approval

    # ------------------------------------------------------------------ #
    # Policies                                                            #
    # ------------------------------------------------------------------ #

    def add_policy_rule(self, rule: PolicyRule) -> PolicyRule:
        self.store.save_policy_rule(rule)
        self.audit.append(
            rule.org_id,
            "policy.saved",
            {"rule_id": rule.rule_id, "effect": rule.effect, "layer": rule.layer.value},
        )
        return rule

    # ------------------------------------------------------------------ #
    # Inspection                                                          #
    # ------------------------------------------------------------------ #

    def session_view(self, org_id: str, session_id: str) -> dict[str, Any]:
        session = self.store.get_session(org_id, session_id)
        if session is None:
            raise NotFoundError(f"session not found: {session_id}")
        steps = self.store.list_trajectory(org_id, session_id)
        decisions = self.store.list_decisions(org_id, session_id=session_id, limit=100)
        intent = self.store.get_intent(org_id, session.intent_id)
        capability = self.store.get_capability(org_id, session.capability_id)
        return {
            "session": session.model_dump(mode="json"),
            "intent": intent.model_dump(mode="json") if intent else None,
            "capability": capability.model_dump(mode="json") if capability else None,
            "trajectory": [s.model_dump(mode="json") for s in steps],
            "decisions": [d.model_dump(mode="json") for d in decisions],
        }

    def metrics_summary(self, org_id: str) -> dict[str, Any]:
        counts = self.store.decision_counts(org_id)
        return {
            "agents": self.store.count("agents", org_id),
            "intents": self.store.count("intents", org_id),
            "sessions": self.store.count("sessions", org_id),
            "capabilities": self.store.count("capabilities", org_id),
            "decisions": self.store.count("decisions", org_id),
            "allowed": counts.get("allow", 0),
            "blocked": counts.get("block", 0),
            "escalated": counts.get("escalate", 0),
            "pending_approvals": len(self.store.list_approvals(org_id, None)),
        }

    def verify_audit(self, org_id: str) -> dict[str, Any]:
        return self.audit.verify(org_id)
