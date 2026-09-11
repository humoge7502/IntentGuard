"""The Action Firewall (§6) — IntentGuard's security core.

Every proposed consequential action passes through an ordered check pipeline.
The LLM/agent proposes; this pipeline decides. Outcomes:

- ALLOW  — action is within identity, capability, policy, intent, context,
           and trajectory bounds; it may execute.
- BLOCK  — a hard boundary was crossed (identity, capability, policy,
           constraint, replay, credential-harvest pattern, critical risk).
- ESCALATE — the action is plausible but uncertain or explicitly gated;
           a human approval bound to this exact action digest is required.

Every decision is explainable (structured reason codes + per-check results),
versioned (intent/capability/policy), risk-scored, persisted, hash-chained
into the audit log, and streamed to the UI.
"""
from __future__ import annotations

import time
from decimal import Decimal, InvalidOperation
from typing import Any

from intentguard.approvals.service import ApprovalService
from intentguard.audit.chain import AuditChain
from intentguard.core.canonical import digest_of
from intentguard.core.enums import (
    HIGH_IMPACT_CLASSES,
    CheckStatus,
    Decision,
    RiskBand,
    SideEffectClass,
)
from intentguard.core.schemas import (
    ActionProposal,
    CheckResult,
    Capability,
    DecisionRecord,
    IntentSpec,
    Observation,
    RiskSignal,
    TrajectoryStep,
    utcnow,
)
from intentguard.firewall.bus import EventBus
from intentguard.policy.engine import PolicyEngine
from intentguard.risk.engine import RiskEngine
from intentguard.storage.store import IntentGuardStore
from intentguard.tools.base import ToolRegistry
from intentguard.trajectory.analysis import TrajectoryAnalyzer

EXTERNAL_CONTENT_TOOLS = frozenset({"web_browser", "file_store", "agent_inbox"})


class ActionFirewall:
    def __init__(
        self,
        store: IntentGuardStore,
        registry: ToolRegistry,
        policy_engine: PolicyEngine,
        risk_engine: RiskEngine,
        trajectory_analyzer: TrajectoryAnalyzer,
        approvals: ApprovalService,
        audit: AuditChain,
        events: EventBus,
    ) -> None:
        self._store = store
        self._registry = registry
        self._policy = policy_engine
        self._risk = risk_engine
        self._trajectory = trajectory_analyzer
        self._approvals = approvals
        self._audit = audit
        self._events = events

    # ------------------------------------------------------------------ #
    # digest                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def action_digest(proposal: ActionProposal) -> str:
        """Stable digest of the action's security-relevant content. Used for
        replay detection and approval binding (excludes ids/timestamps)."""
        return digest_of(
            {
                "agent_id": proposal.agent_id,
                "session_id": proposal.session_id,
                "tool": proposal.tool,
                "operation": proposal.operation,
                "params": proposal.params,
            }
        )

    # ------------------------------------------------------------------ #
    # main entry                                                          #
    # ------------------------------------------------------------------ #

    def evaluate(self, proposal: ActionProposal) -> DecisionRecord:
        started = time.perf_counter()
        checks: list[CheckResult] = []
        reasons: list[str] = []
        signals: list[RiskSignal] = []
        escalation_reasons: list[str] = []
        hard = False

        def check(name: str, status: CheckStatus, detail: str = "") -> None:
            checks.append(CheckResult(check=name, status=status, detail=detail))

        def block(reason: str) -> None:
            nonlocal hard
            hard = True
            if reason not in reasons:
                reasons.append(reason)

        def escalate(reason: str) -> None:
            if reason not in escalation_reasons:
                escalation_reasons.append(reason)

        def signal(code: str, detail: str = "") -> None:
            signals.append(self._risk.signal(code, detail))

        # ------------------------------------------------------------------
        # 1) validate_identity — session + agent
        # ------------------------------------------------------------------
        session = self._store.get_session(proposal.org_id, proposal.session_id)
        intent: IntentSpec | None = None
        capability: Capability | None = None
        tool = self._registry.get(proposal.tool)
        side_effect = None
        exposure: tuple[Decimal, str] | None = None
        facts: dict[str, Any] = {}
        org = proposal.org_id

        if session is None:
            check("identity", CheckStatus.FAIL, "unknown session for this organization")
            block("IDENTITY_UNKNOWN_SESSION")
        elif session.status != "active":
            check("identity", CheckStatus.FAIL, "session is closed")
            block("SESSION_CLOSED")
        elif session.org_id != proposal.org_id:
            check("identity", CheckStatus.FAIL, "organization mismatch (tenant boundary)")
            block("IDENTITY_ORG_MISMATCH")
        else:
            org = session.org_id
            agent = self._store.get_agent(org, proposal.agent_id)
            if agent is None:
                check("identity", CheckStatus.FAIL, f"unknown agent {proposal.agent_id}")
                block("IDENTITY_UNKNOWN_AGENT")
            elif proposal.agent_id != session.agent_id:
                check("identity", CheckStatus.FAIL, "proposing agent does not own this session")
                block("IDENTITY_MISMATCH")
            else:
                check("identity", CheckStatus.PASS, f"agent {agent.name}")

        # ------------------------------------------------------------------
        # 2) validate_capability
        # ------------------------------------------------------------------
        if not hard:
            capability = self._store.get_capability(org, session.capability_id)  # type: ignore[union-attr]
            if capability is None:
                check("capability", CheckStatus.FAIL, "session capability missing")
                block("CAPABILITY_MISSING")
            elif capability.agent_id != session.agent_id:  # type: ignore[union-attr]
                check("capability", CheckStatus.FAIL, "capability minted for a different agent")
                block("CAPABILITY_AGENT_MISMATCH")
            elif capability.status.value == "revoked":  # type: ignore[union-attr]
                check("capability", CheckStatus.FAIL, capability.revoked_reason or "revoked")  # type: ignore[union-attr]
                block("CAPABILITY_REVOKED")
            elif capability.expires_at is not None and capability.expires_at < utcnow():  # type: ignore[union-attr]
                check("capability", CheckStatus.FAIL, "capability expired")
                block("CAPABILITY_EXPIRED")
            else:
                check("capability", CheckStatus.PASS, f"v{capability.version}")  # type: ignore[union-attr]

        # ------------------------------------------------------------------
        # 3) validate_tool + 4) validate_operation
        # ------------------------------------------------------------------
        if not hard and capability is not None:
            if tool is None:
                check("tool", CheckStatus.FAIL, f"tool '{proposal.tool}' is not registered")
                block("TOOL_UNKNOWN")
            else:
                try:
                    side_effect = tool.side_effect_class(proposal.operation)
                except Exception:
                    side_effect = None
                if side_effect is None:
                    check("tool", CheckStatus.FAIL, f"operation '{proposal.operation}' unknown for tool '{tool.name}'")
                    block("OPERATION_UNKNOWN")
                else:
                    check("tool", CheckStatus.PASS, f"{tool.name}.{proposal.operation} [{side_effect.value}]")
                    scope = next(
                        (s for s in capability.scopes if s.tool == tool.name),
                        None,
                    )
                    if scope is None or proposal.operation not in scope.operations:
                        check("operation", CheckStatus.FAIL, "operation outside capability scope")
                        block("OPERATION_NOT_PERMITTED")
                    else:
                        check("operation", CheckStatus.PASS, "within capability scope")
                        intent = self._store.get_intent(org, session.intent_id)  # type: ignore[union-attr]
                        if intent is None:
                            check("intent", CheckStatus.FAIL, "session intent missing")
                            block("INTENT_MISSING")
                        elif proposal.operation not in intent.allowed_operations:
                            check("intent", CheckStatus.FAIL, "operation not authorized by the human's intent")
                            block("OPERATION_NOT_INTENDED")
                        else:
                            check("intent", CheckStatus.PASS, f"goal '{intent.goal}'")

        # ------------------------------------------------------------------
        # 5) validate_parameters (structural)
        # ------------------------------------------------------------------
        if not hard and tool is not None and side_effect is not None:
            param_errors = tool.validate_params(proposal.operation, proposal.params)
            if param_errors:
                check("parameters", CheckStatus.FAIL, "; ".join(param_errors))
                block("PARAM_INVALID")
            else:
                check("parameters", CheckStatus.PASS, "shape and required fields valid")
                exposure = tool.financial_exposure(proposal.operation, proposal.params)
                facts = tool.entity_facts(proposal.operation, proposal.params)

        # ------------------------------------------------------------------
        # 6) validate_policy (deny + limits)
        # ------------------------------------------------------------------
        matched_rule_ids: list[str] = []
        if not hard and tool is not None and side_effect is not None:
            outcome = self._policy.evaluate(
                self._store.list_policy_rules(org), tool.name, proposal.operation
            )
            matched_rule_ids = [r.rule_id for r in outcome.matched_rules]
            if outcome.denied_by is not None:
                check("policy", CheckStatus.FAIL, f"denied by {outcome.denied_by.layer.value} rule '{outcome.denied_by.name}'")
                block(outcome.denied_by.reason_code)
            else:
                cap = outcome.caps.get(exposure[1]) if exposure else None
                if exposure is not None and cap is not None and exposure[0] > cap:
                    check("policy", CheckStatus.FAIL, f"policy cap {cap} {exposure[1]} exceeded")
                    block("BUDGET_EXCEEDED_POLICY")
                else:
                    check("policy", CheckStatus.PASS, "no matching deny; caps satisfied")

        # ------------------------------------------------------------------
        # 7) validate_intent_alignment — constraints from the compiled intent
        # ------------------------------------------------------------------
        budget = capability.budget if capability is not None else None
        divergence = False
        if not hard and intent is not None:
            alignment_detail = "no entity constraints applied"
            failed_constraint = False

            for constraint in intent.constraints:
                if constraint.kind == "amount_limit" and exposure is not None:
                    budget = constraint
                    if exposure[1] != constraint.currency:
                        check("intent_alignment", CheckStatus.FAIL, f"currency {exposure[1]} != authorized {constraint.currency}")
                        block("CURRENCY_MISMATCH")
                        failed_constraint = True
                        divergence = True
                    elif exposure[0] > constraint.max_amount:
                        check(
                            "intent_alignment",
                            CheckStatus.FAIL,
                            f"authorized {constraint.max_amount} {constraint.currency}, requested {exposure[0]} {exposure[1]}",
                        )
                        block("AMOUNT_LIMIT_EXCEEDED")
                        divergence = True
                        failed_constraint = True
                elif constraint.kind == "brand_allow" and "brand" in facts:
                    if str(facts["brand"]).lower() not in [b.lower() for b in constraint.allowed]:
                        check("intent_alignment", CheckStatus.FAIL, f"brand '{facts['brand']}' not in {constraint.allowed}")
                        block("BRAND_NOT_ALLOWED")
                        divergence = True
                        failed_constraint = True
                elif constraint.kind == "destination_allow" and "destination" in facts:
                    if str(facts["destination"]).lower().strip() not in [d.lower().strip() for d in constraint.allowed]:
                        check("intent_alignment", CheckStatus.FAIL, f"destination '{facts['destination']}' not in {constraint.allowed}")
                        block("DESTINATION_NOT_ALLOWED")
                        divergence = True
                        failed_constraint = True
                elif constraint.kind == "quantity_max" and "quantity" in facts:
                    try:
                        requested_qty = int(facts["quantity"])
                    except (TypeError, ValueError):
                        requested_qty = None
                    if requested_qty is not None and requested_qty > constraint.max_quantity:
                        check("intent_alignment", CheckStatus.FAIL, f"quantity {requested_qty} > authorized {constraint.max_quantity}")
                        block("QUANTITY_EXCEEDED")
                        divergence = True
                        failed_constraint = True
                elif constraint.kind == "time_window":
                    now = utcnow()
                    if constraint.not_after is not None and now > constraint.not_after:
                        check("intent_alignment", CheckStatus.FAIL, "intent time window has passed")
                        block("TIME_WINDOW_EXPIRED")
                        failed_constraint = True
                    elif constraint.not_before is not None and now < constraint.not_before:
                        check("intent_alignment", CheckStatus.FAIL, "before intent time window")
                        block("TIME_WINDOW_NOT_STARTED")
                        failed_constraint = True
                elif constraint.kind == "approval_required" and proposal.operation in constraint.operations:
                    over_threshold = constraint.above_amount is None or (
                        exposure is not None and exposure[0] >= constraint.above_amount
                    )
                    if over_threshold:
                        escalate("APPROVAL_REQUIRED")

            if not failed_constraint:
                check("intent_alignment", CheckStatus.PASS, alignment_detail)

            # Uncertainty, not violation: high-impact financial action with no
            # budget constraint at all must not silently pass (§8, §7).
            if (
                not hard
                and side_effect in HIGH_IMPACT_CLASSES
                and exposure is not None
                and budget is None
            ):
                signal("HIGH_IMPACT_UNSCOPED", "consequential financial action with no budget constraint in intent")
                escalate("UNCERTAIN_NO_BUDGET")

        # ------------------------------------------------------------------
        # 8) validate_context — taint from externally-read content
        # ------------------------------------------------------------------
        observations: list[Observation] = []
        if not hard:
            observations = list(proposal.context)
            stored = self._store.list_observations(org, session.session_id)  # type: ignore[union-attr]
            observations.extend(stored)
            observations = observations[-5:]
            if observations and any(o.contains_instruction_language for o in observations):
                signal("EXTERNAL_READ_RECENT", "agent recently read externally-controlled content")
            taint = False
            for obs in observations:
                if not obs.contains_instruction_language:
                    continue
                for amount_record in obs.extracted_amounts:
                    try:
                        ext_amount = Decimal(str(amount_record.get("amount")))
                    except (InvalidOperation, TypeError):
                        continue
                    if (
                        exposure is not None
                        and exposure[0] >= ext_amount
                        and (budget is None or ext_amount > budget.max_amount)
                    ):
                        signal("EXTERNAL_TAINT", f"requested amount matches externally-sourced figure {ext_amount}")
                        taint = True
                if "brand" in facts and str(facts["brand"]) in obs.extracted_brands and hard:
                    taint = True
                if "destination" in facts and str(facts["destination"]).lower() in [
                    d.lower() for d in obs.extracted_destinations
                ] and hard:
                    taint = True
            if taint:
                if hard:
                    reasons.append("EXTERNAL_INSTRUCTION_TAINT")
                else:
                    escalate("EXTERNAL_INSTRUCTION_TAINT")
            for obs in observations:
                if obs.contains_identity_claims and side_effect in HIGH_IMPACT_CLASSES:
                    signal("SUSPICIOUS_IDENTITY_CLAIM", "recently read content claimed supervisory authority")

        # ------------------------------------------------------------------
        # 9) validate_trajectory
        # ------------------------------------------------------------------
        digest = self.action_digest(proposal)
        degrade = False
        if not hard:
            trajectory = self._trajectory.analyze(
                org, session.session_id, digest, proposal.tool, observations  # type: ignore[union-attr]
            )
            for reason in trajectory.hard_reasons:
                block(reason)
            signals.extend(trajectory.signals)
            degrade = trajectory.degrade
            if degrade and not session.degraded:  # type: ignore[union-attr]
                session.degraded = True  # type: ignore[union-attr]
                self._store.save_session(session)  # type: ignore[union-attr]
                self._audit.append(
                    org,
                    "session.degraded",
                    {"session_id": session.session_id, "reason": "cumulative trajectory risk"},  # type: ignore[union-attr]
                )

        # ------------------------------------------------------------------
        # replay check (independent of trajectory rules)
        # ------------------------------------------------------------------
        if not hard and session is not None:
            if self._store.find_allowed_digest(org, session.session_id, digest):
                check("replay", CheckStatus.FAIL, "identical action already authorized and executed")
                block("REPLAY_SUSPECTED")
            else:
                check("replay", CheckStatus.PASS, "first occurrence of this action digest")

        # ------------------------------------------------------------------
        # degraded session gating
        # ------------------------------------------------------------------
        if not hard and session is not None and (session.degraded or degrade):  # type: ignore[union-attr]
            if side_effect in HIGH_IMPACT_CLASSES:
                escalate("APPROVAL_REQUIRED_SESSION_DEGRADED")

        # ------------------------------------------------------------------
        # 10) calculate_risk + 11) decide
        # ------------------------------------------------------------------
        risk = self._risk.assess(signals)
        approval_id: str | None = None

        if hard:
            decision = Decision.BLOCK
            if divergence:
                signal("INTENT_DIVERGENCE", "action entities diverge from the human's constraints")
                risk = self._risk.assess(signals)
        elif risk.band == RiskBand.CRITICAL:
            decision = Decision.BLOCK
            reasons.append("RISK_CRITICAL")
        elif escalation_reasons or risk.band == RiskBand.HIGH:
            if risk.band == RiskBand.HIGH and not escalation_reasons:
                escalation_reasons.append("RISK_HIGH")
            granted = self._approvals.consume_if_valid(
                org, session.session_id, digest  # type: ignore[union-attr]
            )
            if granted is not None:
                decision = Decision.ALLOW
                approval_id = granted.approval_id
                reasons.append("APPROVAL_GRANTED")
            else:
                decision = Decision.ESCALATE
                reasons.extend(escalation_reasons)
                pending = self._approvals.request(
                    org_id=org,
                    session_id=session.session_id,  # type: ignore[union-attr]
                    intent_id=session.intent_id,  # type: ignore[union-attr]
                    action_digest=digest,
                    action_summary={
                        "tool": proposal.tool,
                        "operation": proposal.operation,
                        "params": proposal.params,
                    },
                    reasons=list(reasons),
                )
                self._events.publish(
                    {"type": "approval", "approval": pending.model_dump(mode="json")}
                )
        else:
            decision = Decision.ALLOW

        if decision == Decision.BLOCK and divergence and "INTENT_DIVERGENCE" not in reasons:
            reasons.append("INTENT_DIVERGENCE")

        latency_ms = (time.perf_counter() - started) * 1000
        record = DecisionRecord(
            org_id=org,
            action_id=proposal.action_id,
            action_digest=digest,
            session_id=proposal.session_id,
            agent_id=proposal.agent_id,
            intent_id=intent.intent_id if intent else (session.intent_id if session else ""),
            capability_id=capability.capability_id if capability else (session.capability_id if session else ""),
            decision=decision,
            reasons=reasons,
            checks=checks,
            risk=risk,
            versions={
                "intent": intent.version if intent else None,
                "capability": capability.version if capability else None,
                "policy_rules": matched_rule_ids,
                "compiler": intent.compiled_by if intent else None,
                # proposal metadata allows deterministic execution + replay of
                # exactly what was authorized (never agent-supplied later)
                "proposal": {
                    "tool": proposal.tool,
                    "operation": proposal.operation,
                    "params": proposal.params,
                },
            },
            approval_id=approval_id,
            latency_ms=round(latency_ms, 3),
            created_at=utcnow(),
        )
        self._store.save_decision(record)

        step_class = side_effect if side_effect is not None else SideEffectClass.READ
        prior_steps = self._store.list_trajectory(org, record.session_id)
        self._store.append_trajectory_step(
            TrajectoryStep(
                seq=len(prior_steps) + 1,
                session_id=record.session_id,
                action_id=record.action_id,
                tool=proposal.tool,
                operation=proposal.operation,
                side_effect_class=step_class,
                decision=decision,
                reasons=reasons,
                risk_score=risk.score,
                taint=any(s.code.startswith("EXTERNAL") for s in signals),
                created_at=record.created_at,
            )
        )

        self._audit.append(
            org,
            "firewall.decision",
            {
                "decision_id": record.decision_id,
                "decision": decision.value,
                "action_digest": digest,
                "tool": proposal.tool,
                "operation": proposal.operation,
                "reasons": reasons,
                "risk_score": risk.score,
                "risk_band": risk.band.value,
                "session_id": record.session_id,
                "agent_id": record.agent_id,
            },
        )
        self._events.publish(
            {
                "type": "decision",
                "decision": record.model_dump(mode="json"),
            }
        )
        return record
