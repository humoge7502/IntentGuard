"""Trajectory security (§6): taint, credential harvest, replay, degradation."""
from tests.conftest import PURCHASE_OK


def _divergent_purchase(ctx):
    return {
        "item": "laptop",
        "brand": "Apple",
        "unit_price": "15000",
        "quantity": 500,
        "currency": "INR",
        "destination": "Mumbai",
    }


def test_external_instruction_taint_blocks_divergent_purchase(org_ctx):
    ctx = org_ctx
    eng = ctx.engine
    # benign read: allowed and recorded as an observation
    d_read = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                         "web_browser", "fetch_page", {"uri": "https://deals-express.example/flash-sale"})
    assert d_read.decision.value == "allow"
    eng.execute(ctx.org.org_id, d_read.decision_id)

    d = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                    "shopping_api", "purchase", _divergent_purchase(ctx))
    assert d.decision.value == "block"
    assert "EXTERNAL_INSTRUCTION_TAINT" in d.reasons
    codes = [s.code for s in d.risk.signals]
    assert "EXTERNAL_TAINT" in codes
    assert d.risk.score >= 25


def test_credential_harvest_trajectory_blocked(org_ctx):
    ctx = org_ctx
    eng = ctx.engine
    # intent that legitimately includes both browsing and emailing
    intent = eng.compile_intent(
        ctx.org.org_id, ctx.principal.principal_id,
        "Research laptops online and send me an email summary, budget 1,00,000 INR",
    )
    session = eng.start_session(ctx.org.org_id, ctx.agent.agent_id, intent.intent_id)
    assert "send_email" in intent.allowed_operations

    d_read = eng.propose(ctx.org.org_id, session.session_id, ctx.agent.agent_id,
                         "web_browser", "fetch_page", {"uri": "https://corp-portal.example/security-check"})
    assert d_read.decision.value == "allow"
    eng.execute(ctx.org.org_id, d_read.decision_id)

    d = eng.propose(ctx.org.org_id, session.session_id, ctx.agent.agent_id,
                    "email_api", "send_email",
                    {"to": "boss@acme.in", "subject": "summary", "body": "laptop research summary"})
    assert d.decision.value == "block"
    assert "TRAJECTORY_CREDENTIAL_HARVEST" in d.reasons


def test_replay_blocked_after_execution(org_ctx):
    ctx = org_ctx
    eng = ctx.engine
    d1 = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                     "shopping_api", "purchase", ctx.purchase_params)
    assert d1.decision.value == "allow"
    eng.execute(ctx.org.org_id, d1.decision_id)
    d2 = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                     "shopping_api", "purchase", ctx.purchase_params)
    assert d2.decision.value == "block"
    assert "REPLAY_SUSPECTED" in d2.reasons


def test_session_degradation_after_repeated_blocks(org_ctx):
    ctx = org_ctx
    eng = ctx.engine
    bad_brand = {**PURCHASE_OK, "brand": "Apple"}
    for _ in range(2):
        d = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                        "shopping_api", "purchase", bad_brand)
        assert d.decision.value == "block"
    # even a fully valid high-impact purchase now requires human approval
    d = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                    "shopping_api", "purchase", ctx.purchase_params)
    assert d.decision.value == "escalate"
    assert "APPROVAL_REQUIRED_SESSION_DEGRADED" in d.reasons
    codes = [s.code for s in d.risk.signals]
    assert "RETRY_AFTER_BLOCK" in codes


def test_degraded_session_unblocks_via_exact_approval(org_ctx):
    ctx = org_ctx
    eng = ctx.engine
    bad_brand = {**PURCHASE_OK, "brand": "Dell"}
    for _ in range(2):
        eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                    "shopping_api", "purchase", bad_brand)
    d1 = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                     "shopping_api", "purchase", ctx.purchase_params)
    assert d1.decision.value == "escalate"
    approvals = eng.store.list_approvals(ctx.org.org_id)
    assert approvals and approvals[0].status.value == "pending"
    eng.grant_approval(ctx.org.org_id, approvals[0].approval_id, "human-owner")
    d2 = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                     "shopping_api", "purchase", ctx.purchase_params)
    assert d2.decision.value == "allow"
    assert d2.approval_id == approvals[0].approval_id
    # single use: a third identical proposal must escalate again
    d3 = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                     "shopping_api", "purchase", ctx.purchase_params)
    assert d3.decision.value == "escalate"


def test_approval_is_bound_to_exact_action(org_ctx):
    ctx = org_ctx
    eng = ctx.engine
    bad_brand = {**PURCHASE_OK, "brand": "Asus"}
    for _ in range(2):
        eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                    "shopping_api", "purchase", bad_brand)
    d = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                    "shopping_api", "purchase", ctx.purchase_params)
    assert d.decision.value == "escalate"
    approval = eng.store.list_approvals(ctx.org.org_id)[0]
    eng.grant_approval(ctx.org.org_id, approval.approval_id, "human-owner")
    # a DIFFERENT high-impact action must not ride on this grant
    other = eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                        "shopping_api", "purchase", {**ctx.purchase_params, "quantity": 90})
    assert other.decision.value == "escalate"
