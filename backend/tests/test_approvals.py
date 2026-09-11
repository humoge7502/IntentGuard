"""Approval lifecycle: escalation → grant/deny → single-use consumption."""
from datetime import timedelta

import pytest

from intentguard.core.errors import ConflictError
from intentguard.core.schemas import utcnow


def _escalating_session(engine, org_id, principal_id):
    """Purchase intent with no budget → high-impact financial action escalates."""
    intent = engine.compile_intent(org_id, principal_id, "Buy 10 Apple MacBook laptops")
    agent = engine.register_agent(org_id, principal_id, "mac-buyer")
    session = engine.start_session(org_id, agent.agent_id, intent.intent_id)
    return agent, session


PARAMS = {"item": "laptop", "brand": "Apple", "unit_price": "249900", "quantity": 10,
          "currency": "INR", "destination": "Chennai"}


def test_no_budget_purchase_escalates_then_allows_after_grant(engine, org_ctx):
    org_id, principal_id = org_ctx.org.org_id, org_ctx.principal.principal_id
    agent, session = _escalating_session(engine, org_id, principal_id)

    d1 = engine.propose(org_id, session.session_id, agent.agent_id, "shopping_api", "purchase", PARAMS)
    assert d1.decision.value == "escalate"
    assert "UNCERTAIN_NO_BUDGET" in d1.reasons

    pending = engine.store.list_approvals(org_id)
    assert len(pending) == 1
    assert pending[0].action_summary["operation"] == "purchase"

    engine.grant_approval(org_id, pending[0].approval_id, "human-owner")
    d2 = engine.propose(org_id, session.session_id, agent.agent_id, "shopping_api", "purchase", PARAMS)
    assert d2.decision.value == "allow"
    assert "APPROVAL_GRANTED" in d2.reasons
    consumed = engine.store.get_approval(org_id, pending[0].approval_id)
    assert consumed.status.value == "consumed"


def test_denied_approval_blocks_retry_escalation(engine, org_ctx):
    org_id, principal_id = org_ctx.org.org_id, org_ctx.principal.principal_id
    agent, session = _escalating_session(engine, org_id, principal_id)
    d = engine.propose(org_id, session.session_id, agent.agent_id, "shopping_api", "purchase", PARAMS)
    assert d.decision.value == "escalate"
    approval = engine.store.list_approvals(org_id)[0]
    engine.deny_approval(org_id, approval.approval_id, "human-owner")
    d2 = engine.propose(org_id, session.session_id, agent.agent_id, "shopping_api", "purchase", PARAMS)
    assert d2.decision.value == "escalate"


def test_expired_approval_request(engine, org_ctx):
    org_id, principal_id = org_ctx.org.org_id, org_ctx.principal.principal_id
    agent, session = _escalating_session(engine, org_id, principal_id)
    d = engine.propose(org_id, session.session_id, agent.agent_id, "shopping_api", "purchase", PARAMS)
    approval = engine.store.list_approvals(org_id)[0]
    approval.expires_at = utcnow() - timedelta(seconds=1)
    engine.store.save_approval(approval)
    with pytest.raises(ConflictError):
        engine.grant_approval(org_id, approval.approval_id, "human-owner")


def test_grant_cannot_be_reused_for_different_action(engine, org_ctx):
    org_id, principal_id = org_ctx.org.org_id, org_ctx.principal.principal_id
    agent, session = _escalating_session(engine, org_id, principal_id)
    d = engine.propose(org_id, session.session_id, agent.agent_id, "shopping_api", "purchase", PARAMS)
    approval = engine.store.list_approvals(org_id)[0]
    engine.grant_approval(org_id, approval.approval_id, "human-owner")
    tampered = {**PARAMS, "quantity": 11}
    d2 = engine.propose(org_id, session.session_id, agent.agent_id, "shopping_api", "purchase", tampered)
    assert d2.decision.value == "escalate"


def test_double_grant_rejected(engine, org_ctx):
    org_id, principal_id = org_ctx.org.org_id, org_ctx.principal.principal_id
    agent, session = _escalating_session(engine, org_id, principal_id)
    engine.propose(org_id, session.session_id, agent.agent_id, "shopping_api", "purchase", PARAMS)
    approval = engine.store.list_approvals(org_id)[0]
    engine.grant_approval(org_id, approval.approval_id, "human-owner")
    with pytest.raises(ConflictError):
        engine.grant_approval(org_id, approval.approval_id, "human-owner")
