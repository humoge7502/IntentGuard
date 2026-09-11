"""API authentication: hashed API keys, role model, tenant scoping.

Keys are shown once at creation; only the SHA-256 hash is stored. Every
request's org_id comes from the key — never from the payload — so cross-tenant
access requires a valid key of the target tenant.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Request

from intentguard.core.errors import PermissionDeniedError

ROLE_RANK = {"viewer": 0, "agent": 1, "admin": 2}


@dataclass(frozen=True)
class AuthContext:
    org_id: str
    principal_id: str
    role: str
    key_id: str

    def require_role(self, minimum: str) -> "AuthContext":
        if ROLE_RANK[self.role] < ROLE_RANK[minimum]:
            raise PermissionDeniedError(f"requires {minimum} role; key role is {self.role}")
        return self


def _extract_key(request: Request, query_key: str | None = None) -> str:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    api_key = request.headers.get("x-api-key", "")
    if api_key:
        return api_key.strip()
    # EventSource cannot set headers; SSE accepts a key query param.
    if query_key:
        return query_key.strip()
    raise PermissionDeniedError("missing API key (Authorization: Bearer or X-API-Key)")


def resolve_auth(request: Request, query_key: str | None = None):
    engine = request.app.state.engine
    plaintext = _extract_key(request, query_key)
    key_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    record = engine.store.get_api_key_by_hash(key_hash)
    if record is None:
        raise PermissionDeniedError("invalid API key")
    if record.revoked:
        raise PermissionDeniedError("API key revoked")
    return AuthContext(
        org_id=record.org_id,
        principal_id=record.principal_id,
        role=record.role,
        key_id=record.key_id,
    )


async def get_auth(request: Request):
    return resolve_auth(request)


async def get_admin(request: Request):
    return (await get_auth(request)).require_role("admin")


async def get_agent_role(request: Request):
    return (await get_auth(request)).require_role("agent")
