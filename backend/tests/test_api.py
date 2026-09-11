"""HTTP API: auth, roles, tenant scoping, core endpoints, security headers."""
import pytest
from fastapi.testclient import TestClient

from intentguard.api.app import create_app
from intentguard.config import Settings
from intentguard.engine import IntentGuardEngine
from intentguard.storage.sql import SqlStore
from tests.conftest import INTENT_TEXT, PURCHASE_OK


@pytest.fixture()
def api():
    store = SqlStore("sqlite://")
    engine = IntentGuardEngine(store, settings=Settings(store_kind="memory", bootstrap_admin=False))
    app = create_app(engine=engine, settings=Settings(store_kind="memory", bootstrap_admin=False))

    org = engine.create_organization("HTTP Org")
    principal = engine.create_principal(org.org_id, "Admin")
    _, admin_key = engine.create_api_key(org.org_id, principal.principal_id, "admin")
    _, agent_key = engine.create_api_key(org.org_id, principal.principal_id, "agent")
    _, viewer_key = engine.create_api_key(org.org_id, principal.principal_id, "viewer")

    client = TestClient(app)
    client.headers.update({"X-API-Key": admin_key})
    yield SimpleNamespace(client=client, app=app, engine=engine, org=org, admin_key=admin_key,
                          agent_key=agent_key, viewer_key=viewer_key)
    store.close()


from types import SimpleNamespace  # noqa: E402


def test_health(api):
    r = api.client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_missing_key_rejected(api):
    fresh = TestClient(api.app)
    r = fresh.get("/api/v1/intents")
    assert r.status_code == 403


def test_invalid_key_rejected(api):
    r = api.client.get("/api/v1/intents", headers={"X-API-Key": "ig_garbage"})
    assert r.status_code == 403


def test_role_enforcement(api):
    intent = api.client.post("/api/v1/intents", json={"text": INTENT_TEXT}).json()
    agent = api.client.post(
        "/api/v1/agents", json={"name": "worker-agent"}
    ).json()
    session = api.client.post(
        "/api/v1/sessions", json={"agent_id": agent["agent_id"], "intent_id": intent["intent_id"]}
    ).json()

    # viewer can read but not evaluate
    r = api.client.get("/api/v1/intents", headers={"X-API-Key": api.viewer_key})
    assert r.status_code == 200
    r = api.client.post(
        "/api/v1/firewall/evaluate",
        headers={"X-API-Key": api.viewer_key},
        json={"session_id": session["session_id"], "agent_id": agent["agent_id"],
              "tool": "shopping_api", "operation": "search_products", "params": {"query": "laptop"}},
    )
    assert r.status_code == 403

    # agent can evaluate but not mint policies or grant approvals
    r = api.client.post(
        "/api/v1/policies",
        headers={"X-API-Key": api.agent_key},
        json={"layer": "organization", "name": "x", "effect": "deny"},
    )
    assert r.status_code == 403


def test_intent_lifecycle_over_http(api):
    r = api.client.post("/api/v1/intents", json={"text": INTENT_TEXT})
    assert r.status_code == 201
    intent = r.json()
    assert intent["goal"] == "purchase_laptop"
    graph = api.client.get(f"/api/v1/intents/{intent['intent_id']}/graph").json()
    assert any(n["type"] == "goal" for n in graph["nodes"])


def test_evaluate_and_execute_over_http(api):
    intent = api.client.post("/api/v1/intents", json={"text": INTENT_TEXT}).json()
    agent = api.client.post("/api/v1/agents", json={"name": "procurement"}).json()
    session = api.client.post(
        "/api/v1/sessions", json={"agent_id": agent["agent_id"], "intent_id": intent["intent_id"]}
    ).json()
    r = api.client.post(
        "/api/v1/firewall/evaluate",
        json={"session_id": session["session_id"], "agent_id": agent["agent_id"],
              "tool": "shopping_api", "operation": "purchase", "params": PURCHASE_OK},
    )
    assert r.status_code == 200
    decision = r.json()
    assert decision["decision"] == "allow"
    r2 = api.client.post("/api/v1/firewall/execute", json={"decision_id": decision["decision_id"]})
    assert r2.status_code == 200
    assert r2.json()["ok"] is True
    # executing the same decision twice is rejected
    r3 = api.client.post("/api/v1/firewall/execute", json={"decision_id": decision["decision_id"]})
    assert r3.status_code == 409


def test_blocked_action_explains_over_http(api):
    intent = api.client.post("/api/v1/intents", json={"text": INTENT_TEXT}).json()
    agent = api.client.post("/api/v1/agents", json={"name": "procurement"}).json()
    session = api.client.post(
        "/api/v1/sessions", json={"agent_id": agent["agent_id"], "intent_id": intent["intent_id"]}
    ).json()
    tampered = {**PURCHASE_OK, "quantity": 500}
    r = api.client.post(
        "/api/v1/firewall/evaluate",
        json={"session_id": session["session_id"], "agent_id": agent["agent_id"],
              "tool": "shopping_api", "operation": "purchase", "params": tampered},
    )
    decision = r.json()
    assert decision["decision"] == "block"
    assert "AMOUNT_LIMIT_EXCEEDED" in decision["reasons"]


def test_policy_end_to_end_over_http(api):
    intent = api.client.post("/api/v1/intents", json={"text": INTENT_TEXT}).json()
    agent = api.client.post("/api/v1/agents", json={"name": "procurement"}).json()
    session = api.client.post(
        "/api/v1/sessions", json={"agent_id": agent["agent_id"], "intent_id": intent["intent_id"]}
    ).json()
    r = api.client.post(
        "/api/v1/policies",
        json={"layer": "organization", "name": "no-purchases", "effect": "deny",
              "tool": "shopping_api", "operation": "purchase", "reason_code": "ORG_RULE"},
    )
    assert r.status_code == 201
    r2 = api.client.post(
        "/api/v1/firewall/evaluate",
        json={"session_id": session["session_id"], "agent_id": agent["agent_id"],
              "tool": "shopping_api", "operation": "purchase", "params": PURCHASE_OK},
    )
    assert r2.json()["decision"] == "block"
    assert "ORG_RULE" in r2.json()["reasons"]


def test_tenant_isolation_over_http(api):
    # a second org with its own key
    other_org = api.engine.create_organization("Other Org")
    other_principal = api.engine.create_principal(other_org.org_id, "Other Admin")
    _, other_key = api.engine.create_api_key(other_org.org_id, other_principal.principal_id, "admin")

    intent = api.client.post("/api/v1/intents", json={"text": INTENT_TEXT}).json()
    # other org's admin cannot see or use this org's intent
    r = api.client.get(f"/api/v1/intents/{intent['intent_id']}", headers={"X-API-Key": other_key})
    assert r.status_code == 404
    r = api.client.get("/api/v1/intents", headers={"X-API-Key": other_key})
    assert r.json()["intents"] == []


def test_audit_verify_and_metrics_over_http(api):
    intent = api.client.post("/api/v1/intents", json={"text": INTENT_TEXT}).json()
    events = api.client.get("/api/v1/audit").json()["events"]
    assert len(events) >= 2
    verdict = api.client.post("/api/v1/audit/verify").json()
    assert verdict["valid"] is True
    metrics = api.client.get("/api/v1/metrics/summary").json()
    assert metrics["intents"] >= 1


def test_security_headers_present(api):
    r = api.client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"


def test_rate_limit_trips(api):
    from intentguard.api.app import RateLimiter
    limiter = RateLimiter(per_minute=3)
    for _ in range(3):
        limiter.check("key-1")
    from intentguard.core.errors import RateLimitError
    with pytest.raises(RateLimitError):
        limiter.check("key-1")


def test_demo_endpoints(api):
    r1 = api.client.post("/api/v1/demo/intent_divergence/run")
    assert r1.status_code == 200
    body = r1.json()
    assert body["outcome"] == "block"
    assert any("EXTERNAL_INSTRUCTION_TAINT" in s["reasons"] for s in body["steps"] if s["seq"] == 4)
    r2 = api.client.post("/api/v1/demo/trajectory_credential_harvest/run")
    assert r2.status_code == 200
    assert r2.json()["outcome"] == "block"


def test_unknown_demo_404(api):
    r = api.client.post("/api/v1/demo/does_not_exist/run")
    assert r.status_code == 404


def test_event_bus_pubsub(api):
    q = api.engine.events.subscribe()
    api.engine.events.publish({"type": "decision", "decision": {"x": 1}})
    got = q.get(timeout=1)
    assert got["type"] == "decision"
    api.engine.events.unsubscribe(q)
    api.engine.events.publish({"type": "decision", "decision": {"x": 2}})
    assert q.empty()
