"""Round-3 additions: input-size caps, session lifecycle, and a true E2E
against a real uvicorn process over real HTTP (including SSE streaming,
which the starlette TestClient cannot consume — see docs/AUDIT.md)."""

import json
import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest

from tests.conftest import INTENT_TEXT, PURCHASE_OK

BACKEND_DIR = Path(__file__).resolve().parents[1]


@pytest.fixture()
def api():
    """Local copy of the HTTP fixture (module-scoped fixtures don't cross files)."""
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from intentguard.api.app import create_app
    from intentguard.config import Settings
    from intentguard.engine import IntentGuardEngine
    from intentguard.storage.sql import SqlStore

    store = SqlStore("sqlite://")
    engine = IntentGuardEngine(store, settings=Settings(store_kind="memory", bootstrap_admin=False))
    app = create_app(engine=engine, settings=Settings(store_kind="memory", bootstrap_admin=False))
    org = engine.create_organization("R3 Org")
    principal = engine.create_principal(org.org_id, "Admin")
    _, admin_key = engine.create_api_key(org.org_id, principal.principal_id, "admin")
    client = TestClient(app)
    client.headers.update({"X-API-Key": admin_key})
    yield SimpleNamespace(client=client, app=app, engine=engine, org=org)
    store.close()


def test_oversized_params_rejected(api):
    """BUG-007 prevention: params are capped at 32 KiB serialized so a hostile
    agent cannot amplify memory/storage through decision + audit records."""
    big_param = {"item": "laptop", "brand": "Lenovo", "unit_price": "9500",
                 "quantity": 100, "currency": "INR", "destination": "Chennai",
                 "pad": "x" * 40_000}
    r = api.client.post(
        "/api/v1/firewall/evaluate",
        json={"session_id": "ses_x", "agent_id": "agt_x", "tool": "shopping_api",
              "operation": "purchase", "params": big_param},
    )
    assert r.status_code == 422
    assert r.json()["error"] == "VALIDATION_ERROR"


def test_context_observation_cap(api):
    """Context observations are capped at 20 per proposal."""
    obs = {"source_type": "webpage", "uri": "https://x.example/", "content_digest": "0" * 64}
    r = api.client.post(
        "/api/v1/firewall/evaluate",
        json={"session_id": "ses_x", "agent_id": "agt_x", "tool": "shopping_api",
              "operation": "search_products", "params": {"query": "laptop"},
              "context": [obs] * 21},
    )
    assert r.status_code == 422


def test_session_close_blocks_proposals(org_ctx):
    """Sessions are explicitly closable; a closed session rejects proposals
    with SESSION_CLOSED while keeping history for audit/replay."""
    ctx = org_ctx
    engine = ctx.engine
    session_id = ctx.session.session_id
    org_id = ctx.org.org_id

    closed = engine.close_session(org_id, session_id)
    assert closed.status == "closed"
    # idempotent
    assert engine.close_session(org_id, session_id).status == "closed"

    decision = engine.propose(
        org_id, session_id, ctx.agent.agent_id,
        "shopping_api", "search_products", {"query": "laptop"},
    )
    assert decision.decision.value == "block"
    assert "SESSION_CLOSED" in decision.reasons

    # audit records the lifecycle event
    events = engine.store.list_audit_events(org_id, limit=1000)
    assert any(e.event_type == "session.closed" for e in events)


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def live_server(tmp_path_factory):
    """A REAL uvicorn process on a real port — the deployment-shaped server,
    not the TestClient."""
    tmp = tmp_path_factory.mktemp("e2e")
    db_path = tmp / "e2e.db"
    log_path = tmp / "server.log"
    port = _free_port()
    env = {
        **os.environ,
        "INTENTGUARD_SQLITE_PATH": str(db_path),
        "INTENTGUARD_BOOTSTRAP_ADMIN": "1",
        "INTENTGUARD_RATE_LIMIT_PER_MIN": "10000",
    }
    with log_path.open("w", encoding="utf-8") as log_file:
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "--factory",
             "intentguard.api.app:create_app", "--host", "127.0.0.1",
             "--port", str(port)],
            cwd=str(BACKEND_DIR), env=env,
            stdout=log_file, stderr=subprocess.STDOUT,
        )
        base = f"http://127.0.0.1:{port}"
        try:
            deadline = time.time() + 40
            last_error: Exception | None = None
            while time.time() < deadline:
                try:
                    r = httpx.get(f"{base}/health", timeout=2)
                    if r.status_code == 200:
                        break
                except Exception as exc:  # server still booting
                    last_error = exc
                time.sleep(0.5)
            else:
                raise RuntimeError(f"server did not become healthy: {last_error}")
            key_text = ""
            for _ in range(20):
                key_text = log_path.read_text(encoding="utf-8", errors="replace")
                if "ig_" in key_text:
                    break
                time.sleep(0.5)
            key = next(part for part in key_text.split() if part.startswith("ig_"))
            yield base, key, tmp
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def test_e2e_full_journey_with_live_sse(live_server):
    """E2E over real HTTP: auth → intent → agent → session → allow+execute →
    blocked attack → session close → and an SSE event read over a genuine
    streaming connection (TestClient cannot do this; see docs/AUDIT.md)."""
    base, key, tmp = live_server
    headers = {"X-API-Key": key}
    limits = httpx.Timeout(15.0, read=10.0)

    with httpx.Client(base_url=base, headers=headers, timeout=limits) as client:
        # unauthenticated request is rejected before anything else
        anon = httpx.get(f"{base}/api/v1/intents", timeout=5)
        assert anon.status_code == 403

        intent = client.post("/api/v1/intents",
                             json={"text": INTENT_TEXT}).json()
        agent = client.post("/api/v1/agents", json={"name": "e2e-agent"}).json()
        session = client.post(
            "/api/v1/sessions",
            json={"agent_id": agent["agent_id"], "intent_id": intent["intent_id"]},
        ).json()

        # benign purchase: allow → execute (exactly once over HTTP)
        decision = client.post("/api/v1/firewall/evaluate", json={
            "session_id": session["session_id"], "agent_id": agent["agent_id"],
            "tool": "shopping_api", "operation": "purchase", "params": PURCHASE_OK,
        }).json()
        assert decision["decision"] == "allow"
        executed = client.post("/api/v1/firewall/execute",
                               json={"decision_id": decision["decision_id"]})
        assert executed.status_code == 200 and executed.json()["ok"] is True
        replay = client.post("/api/v1/firewall/execute",
                             json={"decision_id": decision["decision_id"]})
        assert replay.status_code == 409

        # injected attack: blocked with reason codes
        attack = client.post("/api/v1/firewall/evaluate", json={
            "session_id": session["session_id"], "agent_id": agent["agent_id"],
            "tool": "shopping_api", "operation": "purchase",
            "params": {**PURCHASE_OK, "brand": "Apple", "quantity": 500,
                       "unit_price": "15000", "destination": "Mumbai"},
        }).json()
        assert attack["decision"] == "block"
        assert "BRAND_NOT_ALLOWED" in attack["reasons"]

        # session close then rejection
        client.post(f"/api/v1/sessions/{session['session_id']}/close")
        after_close = client.post("/api/v1/firewall/evaluate", json={
            "session_id": session["session_id"], "agent_id": agent["agent_id"],
            "tool": "shopping_api", "operation": "search_products",
            "params": {"query": "laptop"},
        }).json()
        assert "SESSION_CLOSED" in after_close["reasons"]

    # ---- SSE over a genuine streaming connection ----
    # Measured on this machine (see docs/AUDIT.md): a demo POST takes ~1.1-1.3s
    # on fresh Windows connections whether or not a stream is open — the
    # server does not stall unrelated requests while streaming. So: fire the
    # demo first, join the thread, then read — the decision is already queued
    # and the generator's blocked queue-get returns immediately.
    with httpx.Client(base_url=base, headers=headers, timeout=limits) as client:
        token = client.post("/api/v1/events/token").json()["stream_token"]

        def fire() -> None:
            httpx.post(f"{base}/api/v1/demo/intent_divergence/run",
                       headers=headers, timeout=30)

        with client.stream("GET", f"/api/v1/events/stream?stream_token={token}") as resp:
            assert resp.status_code == 200

            t = threading.Thread(target=fire, daemon=True)
            t.start()
            t.join(timeout=30)

            # single pass over the stream (iter_lines is single-consumption):
            # first frame is the ": connected" comment, then the queued decision
            got_connected = False
            got_decision = False
            deadline = time.time() + 25
            for line in resp.iter_lines():
                if line.startswith(":"):
                    got_connected = True
                if line.startswith("data:"):
                    event = json.loads(line[5:].strip())
                    if event.get("type") == "decision":
                        got_decision = True
                        assert event["decision"]["org_id"]
                        break
                if time.time() > deadline:
                    break
            assert got_connected, "expected the : connected comment frame"
            assert got_decision, "live SSE did not deliver a decision event"
