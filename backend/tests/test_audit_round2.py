"""Round-2 audit regression tests. Each test maps to a BUG- id in
docs/AUDIT.md and would have failed before the fix."""

import threading

import pytest
from sqlalchemy import text as sql_text

from intentguard.api.app import RateLimiter
from intentguard.core.errors import ConflictError
from tests.conftest import INTENT_TEXT, PURCHASE_OK


def test_audit_append_survives_seq_collision(org_ctx, monkeypatch):
    """BUG-001: a stale head read (e.g. concurrent appender) must trigger a
    retry against the refreshed head, not an IntegrityError crash."""
    ctx = org_ctx
    chain = ctx.engine.audit
    store = ctx.engine.store
    real_head = store.get_audit_head

    calls = {"n": 0}

    def stale_once(org_id: str):
        # first read during this append returns a deliberately stale head
        if calls["stale_used"] is False:
            calls["stale_used"] = True
            return None  # pretend chain was empty → seq 1, colliding with reality
        return real_head(org_id)

    monkeypatch.setattr(store, "get_audit_head", stale_once)
    calls["stale_used"] = False
    event = chain.append(ctx.org.org_id, "collision.test", {"x": 1})
    assert event.seq == real_head(ctx.org.org_id).seq


def test_audit_concurrent_appends_keep_chain_valid(tmp_path):
    """BUG-001 (concurrency shape): many threads appending to one org must all
    succeed and leave a verifiable chain. Uses a file-backed store: in-memory
    SQLite shares a single connection and cannot model real concurrency."""
    from intentguard.config import Settings
    from intentguard.engine import IntentGuardEngine
    from intentguard.storage.sql import SqlStore

    store = SqlStore(f"sqlite:///{tmp_path / 'race.db'}")
    engine = IntentGuardEngine(store, settings=Settings(store_kind="sqlite"))
    org = engine.create_organization("Race Org")
    errors: list[Exception] = []

    def worker(i: int) -> None:
        try:
            for j in range(5):
                engine.audit.append(org.org_id, "race.test", {"i": i, "j": j})
        except Exception as exc:  # pragma: no cover - surfaced via assert
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)
    assert not errors, errors
    verdict = engine.audit.verify(org.org_id)
    assert verdict["valid"] is True
    assert verdict["events"] == 41  # 40 race events + organization.created
    store.close()


def test_concurrent_execution_has_exactly_one_side_effect(tmp_path):
    """BUG-002: two racing execute() calls on one decision must produce exactly
    one tool side effect; the loser gets ConflictError."""
    from intentguard.config import Settings
    from intentguard.engine import IntentGuardEngine
    from intentguard.storage.sql import SqlStore

    store = SqlStore(f"sqlite:///{tmp_path / 'exec-race.db'}")
    engine = IntentGuardEngine(store, settings=Settings(store_kind="sqlite"))
    org = engine.create_organization("Exec Race Org")
    principal = engine.create_principal(org.org_id, "Owner")
    agent = engine.register_agent(org.org_id, principal.principal_id, "proc")
    intent = engine.compile_intent(org.org_id, principal.principal_id, INTENT_TEXT)
    session = engine.start_session(org.org_id, agent.agent_id, intent.intent_id)

    decision = engine.propose(
        org.org_id, session.session_id, agent.agent_id,
        "shopping_api", "purchase", dict(PURCHASE_OK),
    )
    assert decision.decision.value == "allow"

    results: list[str] = []
    conflicts: list[Exception] = []

    def runner() -> None:
        try:
            engine.execute(org.org_id, decision.decision_id)
            results.append("ok")
        except ConflictError:
            conflicts.append("conflict")

    threads = [threading.Thread(target=runner) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=60)

    assert len(results) == 1, f"side effect ran {len(results)} times"
    assert len(conflicts) == 3
    orders = engine.registry.get("shopping_api").orders
    matching = [o for o in orders if o["session_id"] == session.session_id]
    assert len(matching) == 1, "side effect executed more than once"
    store.close()


def test_pending_approvals_metric_counts_only_pending(engine, org_ctx):
    """BUG-003: escalated-then-granted requests must not stay in the pending count."""
    org_id = org_ctx.org.org_id
    intent = engine.compile_intent(org_id, org_ctx.principal.principal_id, "Buy 10 Apple MacBook laptops")
    session = engine.start_session(org_id, org_ctx.agent.agent_id, intent.intent_id)
    params = {"item": "laptop", "brand": "Apple", "unit_price": "249900",
              "quantity": 10, "currency": "INR", "destination": "Chennai"}
    before = engine.metrics_summary(org_id)["pending_approvals"]
    engine.propose(org_id, session.session_id, org_ctx.agent.agent_id, "shopping_api", "purchase", params)
    during = engine.metrics_summary(org_id)["pending_approvals"]
    approval = engine.store.list_approvals(org_id)[0]
    engine.grant_approval(org_id, approval.approval_id, "human")
    after = engine.metrics_summary(org_id)["pending_approvals"]
    assert during == before + 1
    assert after == before


def test_sqlite_file_store_uses_wal(tmp_path):
    """BUG-004: file-backed SQLite must run in WAL mode with a busy timeout so
    dashboard reads survive benchmark/demo write bursts."""
    from intentguard.storage.sql import SqlStore

    db_path = tmp_path / "wal-check.db"
    store = SqlStore(f"sqlite:///{db_path}")
    with store.engine.connect() as conn:
        mode = conn.execute(sql_text("PRAGMA journal_mode")).scalar()
        busy = conn.execute(sql_text("PRAGMA busy_timeout")).scalar()
    assert str(mode).lower() == "wal"
    assert int(busy) == 30000
    store.close()


def test_rate_limiter_map_is_capped():
    """BUG-006: adversarial key churn must not grow the map without bound."""
    limiter = RateLimiter(per_minute=1000)
    for i in range(RateLimiter.MAX_KEYS + 500):
        limiter.check(f"attacker-key-{i}")
    assert len(limiter._hits) <= RateLimiter.MAX_KEYS


@pytest.fixture()
def api_client():
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from intentguard.api.app import create_app
    from intentguard.config import Settings
    from intentguard.engine import IntentGuardEngine
    from intentguard.storage.sql import SqlStore

    store = SqlStore("sqlite://")
    engine = IntentGuardEngine(store, settings=Settings(store_kind="memory", bootstrap_admin=False))
    app = create_app(engine=engine, settings=Settings(store_kind="memory", bootstrap_admin=False))
    org = engine.create_organization("Stream Org")
    principal = engine.create_principal(org.org_id, "Admin")
    _, admin_key = engine.create_api_key(org.org_id, principal.principal_id, "admin")
    client = TestClient(app)
    client.headers.update({"X-API-Key": admin_key})
    yield SimpleNamespace(client=client, engine=engine, org=org)
    store.close()


def test_stream_token_flow(api_client):
    """BUG-005: the API key must never appear in a URL.

    Transport note (verified 2026-09-12): this environment's starlette 1.6
    TestClient deadlocks on ANY infinite streaming response (minimal repro
    with a bare FastAPI app hangs; httpx2 does not help). The live uvicorn
    server streams correctly — verified in the browser during frontend QA.
    So this test exercises the security logic directly: guard paths over
    plain GET (JSON, no streaming) and the broker's single-use/expiry
    semantics in-process."""

    # no token at all → 403 (plain JSON, no stream starts)
    r = api_client.client.get("/api/v1/events/stream")
    assert r.status_code == 403

    # garbage token → 403
    r2 = api_client.client.get("/api/v1/events/stream?stream_token=st_bogus")
    assert r2.status_code == 403

    # broker semantics: issue → redeem works exactly once → expiry honored
    broker = api_client.client.app.state.stream_tokens
    token = broker.issue(api_client.org.org_id, "admin")
    redeemed = broker.redeem(token)
    assert redeemed is not None and redeemed[0] == api_client.org.org_id
    assert broker.redeem(token) is None  # single use
    expired = broker.issue(api_client.org.org_id, "admin")
    api_client.client.app.state.stream_tokens._tokens[expired] = (
        api_client.org.org_id, "admin", 0.0,
    )
    assert broker.redeem(expired) is None  # expired

    # the token POST requires an authenticated key
    from fastapi.testclient import TestClient as _TC
    fresh = _TC(api_client.client.app)
    assert fresh.post("/api/v1/events/token").status_code == 403


def test_request_id_header_present(api_client):
    r = api_client.client.get("/health")
    assert r.headers.get("x-request-id")
