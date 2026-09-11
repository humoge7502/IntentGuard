"""Tenant isolation (§36): cross-org access must behave as not-found, and the
firewall must refuse cross-tenant sessions outright."""
import pytest

from intentguard.core.errors import NotFoundError
from tests.conftest import INTENT_TEXT, PURCHASE_OK


@pytest.fixture()
def two_orgs(engine):
    def make_org(name):
        org = engine.create_organization(name)
        principal = engine.create_principal(org.org_id, f"{name} owner")
        agent = engine.register_agent(org.org_id, principal.principal_id, f"{name}-agent")
        intent = engine.compile_intent(org.org_id, principal.principal_id, INTENT_TEXT)
        session = engine.start_session(org.org_id, agent.agent_id, intent.intent_id)
        return org, principal, agent, intent, session

    a = make_org("OrgA")
    b = make_org("OrgB")
    return a, b


def test_store_lookups_are_org_scoped(engine, two_orgs):
    (org_a, _, _, intent_a, _), (org_b, _, _, intent_b, _) = two_orgs
    assert engine.store.get_intent(org_a.org_id, intent_b.intent_id) is None
    assert engine.store.get_intent(org_b.org_id, intent_a.intent_id) is None
    with pytest.raises(NotFoundError):
        engine.intent_graph(org_a.org_id, intent_b.intent_id)


def test_firewall_rejects_cross_tenant_session(engine, two_orgs):
    (org_a, _, agent_a, _, _), (org_b, _, _, _, session_b) = two_orgs
    decision = engine.propose(
        org_a.org_id, session_b.session_id, agent_a.agent_id,
        "shopping_api", "purchase", PURCHASE_OK,
    )
    assert decision.decision.value == "block"
    assert decision.reasons[0] in {"IDENTITY_UNKNOWN_SESSION", "IDENTITY_ORG_MISMATCH"}


def test_cross_tenant_execution_impossible(engine, two_orgs):
    (org_a, _, agent_a, _, session_a), (org_b, _, _, _, _) = two_orgs
    d = engine.propose(org_a.org_id, session_a.session_id, agent_a.agent_id,
                       "shopping_api", "purchase", PURCHASE_OK)
    assert d.decision.value == "allow"
    from intentguard.core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        engine.execute(org_b.org_id, d.decision_id)


def test_audit_and_metrics_do_not_leak(engine, two_orgs):
    (org_a, _, agent_a, _, session_a), (org_b, _, _, _, _) = two_orgs
    engine.propose(org_a.org_id, session_a.session_id, agent_a.agent_id,
                   "shopping_api", "purchase", PURCHASE_OK)
    metrics_b = engine.metrics_summary(org_b.org_id)
    assert metrics_b["decisions"] == 0
    events_a = engine.store.list_audit_events(org_a.org_id)
    assert all(e.org_id == org_a.org_id for e in events_a)
