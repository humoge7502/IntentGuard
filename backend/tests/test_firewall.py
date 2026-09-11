"""Firewall pipeline: identity, capability, tool/operation scoping, policy,
intent constraints, decisions metadata."""
import time

import pytest

from intentguard.core.errors import ConflictError


def test_benign_purchase_allowed_and_executed_once(org_ctx):
    ctx = org_ctx
    d = ctx.engine.propose(
        ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
        "shopping_api", "purchase", ctx.purchase_params,
    )
    assert d.decision.value == "allow"
    result = ctx.engine.execute(ctx.org.org_id, d.decision_id)
    assert result.ok
    with pytest.raises(ConflictError):
        ctx.engine.execute(ctx.org.org_id, d.decision_id)


def test_decision_is_fully_attributed(org_ctx):
    ctx = org_ctx
    d = ctx.engine.propose(
        ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
        "shopping_api", "purchase", ctx.purchase_params,
    )
    assert d.org_id == ctx.org.org_id
    assert d.session_id == ctx.session.session_id
    assert d.agent_id == ctx.agent.agent_id
    assert d.intent_id == ctx.intent.intent_id
    assert d.capability_id == ctx.session.capability_id
    assert d.versions["intent"] == ctx.intent.version
    assert d.latency_ms >= 0
    check_names = [c.check for c in d.checks]
    for expected in ("identity", "capability", "tool", "operation", "intent", "parameters", "policy", "intent_alignment", "replay"):
        assert expected in check_names


def test_budget_exceeded_blocked(org_ctx):
    ctx = org_ctx
    params = {**ctx.purchase_params, "quantity": 800}
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", params)
    assert d.decision.value == "block"
    assert "AMOUNT_LIMIT_EXCEEDED" in d.reasons
    assert "INTENT_DIVERGENCE" in d.reasons


def test_unit_price_tampering_blocked(org_ctx):
    ctx = org_ctx
    params = {**ctx.purchase_params, "unit_price": "20000"}
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", params)
    assert d.decision.value == "block"
    assert "AMOUNT_LIMIT_EXCEEDED" in d.reasons


def test_brand_violation_blocked(org_ctx):
    ctx = org_ctx
    params = {**ctx.purchase_params, "brand": "Apple"}
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", params)
    assert d.decision.value == "block"
    assert "BRAND_NOT_ALLOWED" in d.reasons


def test_destination_manipulation_blocked(org_ctx):
    ctx = org_ctx
    params = {**ctx.purchase_params, "destination": "Mumbai"}
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", params)
    assert d.decision.value == "block"
    assert "DESTINATION_NOT_ALLOWED" in d.reasons


def test_quantity_exceeded_blocked(org_ctx):
    ctx = org_ctx
    params = {**ctx.purchase_params, "quantity": 101, "unit_price": "5000"}
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", params)
    assert d.decision.value == "block"
    assert "QUANTITY_EXCEEDED" in d.reasons


def test_currency_switch_blocked(org_ctx):
    ctx = org_ctx
    params = {**ctx.purchase_params, "currency": "USD", "unit_price": "120"}
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", params)
    assert d.decision.value == "block"
    assert "CURRENCY_MISMATCH" in d.reasons


def test_unknown_tool_blocked(org_ctx):
    ctx = org_ctx
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "cloud_api", "deploy", {})
    assert d.decision.value == "block"
    assert "TOOL_UNKNOWN" in d.reasons


def test_unknown_operation_blocked(org_ctx):
    ctx = org_ctx
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "delete_account", {})
    assert d.decision.value == "block"
    assert "OPERATION_UNKNOWN" in d.reasons


def test_operation_outside_capability_blocked(org_ctx):
    ctx = org_ctx
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "banking_api", "get_balance", {"account_id": "acc_main"})
    assert d.decision.value == "block"
    assert "OPERATION_NOT_PERMITTED" in d.reasons


def test_parameter_tampering_extra_fields_blocked(org_ctx):
    ctx = org_ctx
    params = {**ctx.purchase_params, "admin_override": True}
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", params)
    assert d.decision.value == "block"
    assert "PARAM_INVALID" in d.reasons


def test_agent_impersonation_blocked(org_ctx):
    ctx = org_ctx
    other = ctx.engine.register_agent(ctx.org.org_id, ctx.principal.principal_id, "rogue-agent")
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, other.agent_id, "shopping_api", "purchase", ctx.purchase_params)
    assert d.decision.value == "block"
    assert "IDENTITY_MISMATCH" in d.reasons


def test_unknown_session_blocked(org_ctx):
    ctx = org_ctx
    d = ctx.engine.propose(ctx.org.org_id, "ses_does_not_exist", ctx.agent.agent_id, "shopping_api", "purchase", ctx.purchase_params)
    assert d.decision.value == "block"
    assert "IDENTITY_UNKNOWN_SESSION" in d.reasons


def test_org_policy_deny_rule(org_ctx):
    ctx = org_ctx
    from intentguard.core.enums import PolicyLayer
    from intentguard.core.schemas import PolicyRule
    ctx.engine.add_policy_rule(
        PolicyRule(
            org_id=ctx.org.org_id, layer=PolicyLayer.ORGANIZATION, name="no-purchases",
            effect="deny", tool="shopping_api", operation="purchase",
            reason_code="ORG_PURCHASES_DISABLED",
        )
    )
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", ctx.purchase_params)
    assert d.decision.value == "block"
    assert "ORG_PURCHASES_DISABLED" in d.reasons


def test_org_policy_limit_narrows_intent_budget(org_ctx):
    ctx = org_ctx
    from decimal import Decimal

    from intentguard.core.enums import PolicyLayer
    from intentguard.core.schemas import PolicyRule
    ctx.engine.add_policy_rule(
        PolicyRule(
            org_id=ctx.org.org_id, layer=PolicyLayer.ORGANIZATION, name="purchase-cap",
            effect="limit", tool="shopping_api", operation="purchase",
            max_amount=Decimal("200000"), currency="INR",
        )
    )
    # intent budget 1,000,000; policy caps at 200,000 → 100 × 9,500 = 950,000 must block
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "purchase", ctx.purchase_params)
    assert d.decision.value == "block"
    assert "BUDGET_EXCEEDED_POLICY" in d.reasons


def test_capability_revocation_blocks(org_ctx):
    ctx = org_ctx
    ctx.engine.revoke_capability(ctx.org.org_id, ctx.session.capability_id, "offboarding")
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id, "shopping_api", "search_products", {"query": "laptop"})
    assert d.decision.value == "block"
    assert "CAPABILITY_REVOKED" in d.reasons


def test_capability_expiry_blocks(org_ctx):
    ctx = org_ctx
    short = ctx.engine.start_session(ctx.org.org_id, ctx.agent.agent_id, ctx.intent.intent_id, ttl_seconds=1)
    time.sleep(1.2)
    d = ctx.engine.propose(ctx.org.org_id, short.session_id, ctx.agent.agent_id, "shopping_api", "search_products", {"query": "laptop"})
    assert d.decision.value == "block"
    assert "CAPABILITY_EXPIRED" in d.reasons


def test_cross_capability_agent_mismatch(org_ctx, store):
    ctx = org_ctx
    other = ctx.engine.register_agent(ctx.org.org_id, ctx.principal.principal_id, "agent-two")
    session_two = ctx.engine.start_session(ctx.org.org_id, other.agent_id, ctx.intent.intent_id)
    # point session_two at session one's capability (capability minted for agent one)
    session = ctx.engine.store.get_session(ctx.org.org_id, session_two.session_id)
    session.capability_id = ctx.session.capability_id
    ctx.engine.store.save_session(session)
    d = ctx.engine.propose(ctx.org.org_id, session_two.session_id, other.agent_id, "shopping_api", "purchase", ctx.purchase_params)
    assert d.decision.value == "block"
    assert "CAPABILITY_AGENT_MISMATCH" in d.reasons
