"""Audit chain integrity: verification, tamper detection, optional signing."""
import base64

from sqlalchemy import text as sql_text

from intentguard.config import Settings


def test_chain_verifies_after_activity(org_ctx):
    ctx = org_ctx
    d = ctx.engine.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                           "shopping_api", "purchase", ctx.purchase_params)
    ctx.engine.execute(ctx.org.org_id, d.decision_id)
    result = ctx.engine.verify_audit(ctx.org.org_id)
    assert result["valid"] is True
    assert result["events"] > 5


def test_tampering_is_detected(org_ctx):
    ctx = org_ctx
    eng = ctx.engine
    for _ in range(3):
        eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                    "shopping_api", "search_products", {"query": "laptop"})
    # rewrite a payload directly in storage, attacker-style
    with eng.store.engine.begin() as conn:
        conn.execute(sql_text(
            "UPDATE audit_events SET payload_json = '{\"tampered\": true}' "
            "WHERE seq = 2 AND org_id = :org"
        ), {"org": ctx.org.org_id})
    result = eng.verify_audit(ctx.org.org_id)
    assert result["valid"] is False
    assert result["broken_at_seq"] == 2


def test_deletion_is_detected(org_ctx):
    ctx = org_ctx
    eng = ctx.engine
    for _ in range(3):
        eng.propose(ctx.org.org_id, ctx.session.session_id, ctx.agent.agent_id,
                    "shopping_api", "search_products", {"query": "laptop"})
    with eng.store.engine.begin() as conn:
        conn.execute(sql_text("DELETE FROM audit_events WHERE seq = 2 AND org_id = :org"),
                     {"org": ctx.org.org_id})
    result = eng.verify_audit(ctx.org.org_id)
    assert result["valid"] is False


def test_signed_chain_roundtrip():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        NoEncryption,
        PrivateFormat,
    )
    key = Ed25519PrivateKey.generate()
    key_b64 = base64.b64encode(
        key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    ).decode()
    store = __import__("intentguard.storage.sql", fromlist=["SqlStore"]).SqlStore("sqlite://")
    engine = __import__("intentguard.engine", fromlist=["IntentGuardEngine"]).IntentGuardEngine(
        store, settings=Settings(store_kind="memory", audit_signing_key=key_b64)
    )
    org = engine.create_organization("Signed Org")
    for i in range(3):
        engine.audit.append(org.org_id, "test.event", {"i": i})
    assert engine.verify_audit(org.org_id)["valid"] is True
    events = engine.store.list_audit_events(org.org_id)
    assert all(e.signature is not None for e in events)
    # tamper
    with store.engine.begin() as conn:
        conn.execute(sql_text("UPDATE audit_events SET payload_json = '{\"i\": 999}' WHERE seq = 2"))
    assert engine.verify_audit(org.org_id)["valid"] is False
    store.close()


def test_audit_events_are_org_scoped(org_ctx):
    ctx = org_ctx
    other = ctx.engine.create_organization("Other Org")
    ctx.engine.audit.append(other.org_id, "other.event", {"x": 1})
    events = ctx.engine.store.list_audit_events(ctx.org.org_id)
    assert all(e.org_id == ctx.org.org_id for e in events)
