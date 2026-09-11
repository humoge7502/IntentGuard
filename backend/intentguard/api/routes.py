"""Versioned REST API (§34). Every route is tenant-scoped by the API key;
agent-supplied metadata is never trusted."""
from __future__ import annotations

import asyncio
import json
import queue as queue_mod
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from intentguard.api.auth import AuthContext, get_admin, get_agent_role, get_auth
from intentguard.api.schemas import (
    AgentCreate,
    ApprovalAction,
    BenchmarkRun,
    EvaluateRequest,
    ExecuteRequest,
    IntentCreate,
    PolicyRuleCreate,
    RevokeRequest,
    SessionCreate,
)
from intentguard.core.enums import ApprovalStatus
from intentguard.core.errors import NotFoundError, PermissionDeniedError
from intentguard.core.schemas import Observation, PolicyRule

router = APIRouter(prefix="/api/v1")


def engine_of(request: Request):
    return request.app.state.engine


# --------------------------------------------------------------------- #
# identity / meta                                                        #
# --------------------------------------------------------------------- #


@router.get("/me")
def me(request: Request, auth: AuthContext = Depends(get_auth)):
    return {
        "org_id": auth.org_id,
        "principal_id": auth.principal_id,
        "role": auth.role,
        "key_id": auth.key_id,
    }


@router.get("/tools")
def list_tools(request: Request, auth: AuthContext = Depends(get_auth)):
    return {"tools": engine_of(request).registry.list_tools()}


# --------------------------------------------------------------------- #
# intents                                                                #
# --------------------------------------------------------------------- #


@router.post("/intents", status_code=201)
def create_intent(body: IntentCreate, request: Request, auth: AuthContext = Depends(get_agent_role)):
    intent = engine_of(request).compile_intent(auth.org_id, auth.principal_id, body.text)
    return intent.model_dump(mode="json")


@router.get("/intents")
def list_intents(request: Request, auth: AuthContext = Depends(get_auth)):
    intents = engine_of(request).store.list_intents(auth.org_id)
    return {"intents": [i.model_dump(mode="json") for i in intents]}


@router.get("/intents/{intent_id}")
def get_intent(intent_id: str, request: Request, auth: AuthContext = Depends(get_auth)):
    intent = engine_of(request).store.get_intent(auth.org_id, intent_id)
    if intent is None:
        raise NotFoundError(f"intent not found: {intent_id}")
    return intent.model_dump(mode="json")


@router.get("/intents/{intent_id}/graph")
def intent_graph(intent_id: str, request: Request, auth: AuthContext = Depends(get_auth)):
    return engine_of(request).intent_graph(auth.org_id, intent_id)


# --------------------------------------------------------------------- #
# agents & sessions                                                      #
# --------------------------------------------------------------------- #


@router.post("/agents", status_code=201)
def create_agent(body: AgentCreate, request: Request, auth: AuthContext = Depends(get_admin)):
    agent = engine_of(request).register_agent(auth.org_id, auth.principal_id, body.name, body.framework)
    return agent.model_dump(mode="json")


@router.get("/agents")
def list_agents(request: Request, auth: AuthContext = Depends(get_auth)):
    return {"agents": [a.model_dump(mode="json") for a in engine_of(request).store.list_agents(auth.org_id)]}


@router.post("/sessions", status_code=201)
def create_session(body: SessionCreate, request: Request, auth: AuthContext = Depends(get_agent_role)):
    session = engine_of(request).start_session(
        auth.org_id, body.agent_id, body.intent_id, ttl_seconds=body.ttl_seconds
    )
    return session.model_dump(mode="json")


@router.get("/sessions/{session_id}")
def get_session(session_id: str, request: Request, auth: AuthContext = Depends(get_auth)):
    return engine_of(request).session_view(auth.org_id, session_id)


# --------------------------------------------------------------------- #
# firewall                                                               #
# --------------------------------------------------------------------- #


@router.post("/firewall/evaluate")
def evaluate(body: EvaluateRequest, request: Request, auth: AuthContext = Depends(get_agent_role)):
    context = [Observation.model_validate(o) for o in body.context]
    decision = engine_of(request).propose(
        org_id=auth.org_id,
        session_id=body.session_id,
        agent_id=body.agent_id,
        tool=body.tool,
        operation=body.operation,
        params=body.params,
        context=context,
    )
    return decision.model_dump(mode="json")


@router.post("/firewall/execute")
def execute(body: ExecuteRequest, request: Request, auth: AuthContext = Depends(get_agent_role)):
    result = engine_of(request).execute(auth.org_id, body.decision_id)
    return {"ok": result.ok, "data": result.data, "error": result.error}


@router.get("/decisions")
def list_decisions(request: Request, session_id: str | None = None, limit: int = 100,
                   auth: AuthContext = Depends(get_auth)):
    limit = max(1, min(limit, 500))
    decisions = engine_of(request).store.list_decisions(auth.org_id, session_id=session_id, limit=limit)
    return {"decisions": [d.model_dump(mode="json") for d in decisions]}


# --------------------------------------------------------------------- #
# approvals & capabilities                                               #
# --------------------------------------------------------------------- #


@router.get("/approvals")
def list_approvals(request: Request, status: str | None = None, auth: AuthContext = Depends(get_auth)):
    status_filter = ApprovalStatus(status) if status else None
    approvals = engine_of(request).store.list_approvals(auth.org_id, status_filter)
    return {"approvals": [a.model_dump(mode="json") for a in approvals]}


@router.post("/approvals/{approval_id}/grant")
def grant_approval(approval_id: str, body: ApprovalAction, request: Request,
                   auth: AuthContext = Depends(get_admin)):
    approval = engine_of(request).grant_approval(auth.org_id, approval_id, body.approver)
    return approval.model_dump(mode="json")


@router.post("/approvals/{approval_id}/deny")
def deny_approval(approval_id: str, body: ApprovalAction, request: Request,
                  auth: AuthContext = Depends(get_admin)):
    approval = engine_of(request).deny_approval(auth.org_id, approval_id, body.approver)
    return approval.model_dump(mode="json")


@router.post("/capabilities/{capability_id}/revoke")
def revoke_capability(capability_id: str, body: RevokeRequest, request: Request,
                      auth: AuthContext = Depends(get_admin)):
    capability = engine_of(request).revoke_capability(auth.org_id, capability_id, body.reason)
    return capability.model_dump(mode="json")


@router.get("/capabilities")
def list_capabilities(request: Request, auth: AuthContext = Depends(get_auth)):
    return {"capabilities": [c.model_dump(mode="json") for c in engine_of(request).store.list_capabilities(auth.org_id)]}


# --------------------------------------------------------------------- #
# policies                                                               #
# --------------------------------------------------------------------- #


@router.get("/policies")
def list_policies(request: Request, auth: AuthContext = Depends(get_auth)):
    return {"rules": [r.model_dump(mode="json") for r in engine_of(request).store.list_policy_rules(auth.org_id)]}


@router.post("/policies", status_code=201)
def create_policy(body: PolicyRuleCreate, request: Request, auth: AuthContext = Depends(get_admin)):
    rule = PolicyRule(
        org_id=auth.org_id,
        layer=body.layer,  # type: ignore[arg-type]
        name=body.name,
        effect=body.effect,  # type: ignore[arg-type]
        tool=body.tool or None,
        operation=body.operation or None,
        max_amount=Decimal(str(body.max_amount)) if body.max_amount is not None else None,
        currency=body.currency,
        reason_code=body.reason_code,
        description=body.description,
    )
    return engine_of(request).add_policy_rule(rule).model_dump(mode="json")


# --------------------------------------------------------------------- #
# audit & metrics                                                        #
# --------------------------------------------------------------------- #


@router.get("/audit")
def list_audit(request: Request, limit: int = 200, auth: AuthContext = Depends(get_auth)):
    limit = max(1, min(limit, 1000))
    events = engine_of(request).store.list_audit_events(auth.org_id, limit=limit)
    return {"events": [e.model_dump(mode="json") for e in events]}


@router.post("/audit/verify")
def verify_audit(request: Request, auth: AuthContext = Depends(get_admin)):
    return engine_of(request).verify_audit(auth.org_id)


@router.get("/metrics/summary")
def metrics_summary(request: Request, auth: AuthContext = Depends(get_auth)):
    return engine_of(request).metrics_summary(auth.org_id)


# --------------------------------------------------------------------- #
# demo & benchmark                                                       #
# --------------------------------------------------------------------- #


@router.post("/demo/{name}/run")
def run_demo(name: str, request: Request, auth: AuthContext = Depends(get_admin)):
    from intentguard.demo.scenarios import run_demo

    return run_demo(engine_of(request), auth.org_id, name)


@router.post("/benchmarks/run")
def run_benchmark(body: BenchmarkRun, request: Request, auth: AuthContext = Depends(get_admin)):
    from intentguard.attackbench.runner import run_benchmark as run

    return run(engine_of(request), auth.org_id, max_per_family=body.max_per_family)


# --------------------------------------------------------------------- #
# live event stream (SSE)                                                #
# --------------------------------------------------------------------- #


@router.post("/events/token")
def issue_stream_token(request: Request, auth: AuthContext = Depends(get_auth)):
    """Exchange the API key (header-based, never logged) for a single-use,
    60-second stream token. EventSource cannot set headers; a raw key in the
    query string would leak into access/proxy logs — the token is worthless
    beyond one stream connection."""
    broker = request.app.state.stream_tokens
    token = broker.issue(auth.org_id, auth.role)
    return {"stream_token": token, "expires_in": broker.TTL_SECONDS}


@router.get("/events/stream")
async def event_stream(request: Request, stream_token: str | None = None):
    if not stream_token:
        raise PermissionDeniedError("stream_token required (POST /api/v1/events/token)")
    resolved = request.app.state.stream_tokens.redeem(stream_token)
    if resolved is None:
        raise PermissionDeniedError("invalid or expired stream token")
    org_id, _role = resolved
    engine = engine_of(request)
    q = engine.events.subscribe()

    async def generator():
        try:
            yield ": connected\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event = await asyncio.to_thread(q.get, True, 15)
                except queue_mod.Empty:
                    yield ": keepalive\n\n"
                    continue
                # stream is tenant-scoped: drop events from other orgs
                decision_org = (
                    (event.get("decision") or {}).get("org_id")
                    or (event.get("approval") or {}).get("org_id")
                )
                if decision_org is not None and decision_org != org_id:
                    continue
                yield f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
        finally:
            engine.events.unsubscribe(q)

    return StreamingResponse(generator(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})
