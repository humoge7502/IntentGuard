"""FastAPI application factory."""
from __future__ import annotations

import logging
import sys
import time
import uuid
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from intentguard.api.routes import router
from intentguard.config import Settings
from intentguard.core.enums import StoreKind
from intentguard.core.errors import (
    ConflictError,
    IntentGuardError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ValidationError,
)
from intentguard.engine import IntentGuardEngine
from intentguard.storage.sql import SqlStore

_STATUS_BY_ERROR = {
    NotFoundError: 404,
    ValidationError: 422,
    PermissionDeniedError: 403,
    ConflictError: 409,
    RateLimitError: 429,
}

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


class RateLimiter:
    """In-memory sliding window per API key (MVP; use Redis in production).

    The key map is capped: unauthenticated garbage must not grow memory
    without bound (BUG-006 fix).
    """

    MAX_KEYS = 10_000

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        if len(self._hits) >= self.MAX_KEYS and key not in self._hits:
            # evict oldest-inserted entries (dicts preserve insertion order)
            excess = len(self._hits) - self.MAX_KEYS + 1
            for oldest in list(self._hits.keys())[:excess]:
                self._hits.pop(oldest, None)
        hits = self._hits[key]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self.per_minute:
            raise RateLimitError("rate limit exceeded")
        hits.append(now)


class StreamTokenBroker:
    """Single-use, short-TTL tokens for the SSE endpoint.

    Browsers' EventSource cannot set headers, but a raw API key in the URL
    leaks into access/proxy logs (BUG-005). Instead, an authenticated client
    exchanges its key for a single-use stream token that is worthless beyond
    one stream connection for 60 seconds. In-memory by design: tokens die
    with the process, so rotating processes invalidates nothing durable.
    """

    TTL_SECONDS = 60

    def __init__(self) -> None:
        import secrets as _secrets

        self._secrets = _secrets
        self._tokens: dict[str, tuple[str, str, float]] = {}  # token -> (org, role, expires)

    def issue(self, org_id: str, role: str) -> str:
        token = "st_" + self._secrets.token_urlsafe(24)
        self._tokens[token] = (org_id, role, time.monotonic() + self.TTL_SECONDS)
        return token

    def redeem(self, token: str) -> tuple[str, str] | None:
        record = self._tokens.pop(token, None)  # single use
        if record is None:
            return None
        org_id, role, expires = record
        if time.monotonic() > expires:
            return None
        return org_id, role


class RequestContextMiddleware:
    """Pure ASGI middleware: rate limiting, request IDs, access logs, and
    security headers. Pure ASGI (not BaseHTTPMiddleware) because the SSE
    endpoint streams forever — body-wrapping middleware deadlocks on it."""

    def __init__(self, app: Any, rate_limiter: RateLimiter, logger: logging.Logger) -> None:
        self.app = app
        self.rate_limiter = rate_limiter
        self.logger = logger

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        request_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()

        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode()))
                # API responses must never be cached (decision data); public
                # assets set their own cache headers.
                if not path.startswith("/api/"):
                    headers.append((b"cache-control", b"no-store"))
                for header, value in SECURITY_HEADERS.items():
                    if not (header == "Cache-Control" and path.startswith("/api/")):
                        key = header.encode()
                        if not any(k == key for k, _ in headers):
                            headers.append((key, value.encode()))
                message = {**message, "headers": headers}
            await send(message)

        if path.startswith("/api/"):
            headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
            key = headers.get("authorization") or headers.get("x-api-key") or "anon"
            try:
                self.rate_limiter.check(key[:72])
            except RateLimitError:
                message = b'{"error":"RATE_LIMITED","message":"rate limit exceeded"}'
                await send_wrapper(
                    {
                        "type": "http.response.start",
                        "status": 429,
                        "headers": [(b"content-type", b"application/json"),
                                    (b"content-length", str(len(message)).encode())],
                    }
                )
                await send({"type": "http.response.body", "body": message})
                return

        status_holder = {"status": 500}
        original_send = send_wrapper

        async def status_capture(message: Any) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message.get("status", 500)
            await original_send(message)

        try:
            await self.app(scope, receive, status_capture)
        except Exception:
            self.logger.exception(
                "unhandled error request_id=%s path=%s", request_id, path
            )
            raise
        finally:
            # path only — never the query string (stream tokens must not reach logs)
            self.logger.info(
                "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
                request_id,
                scope.get("method", ""),
                path,
                status_holder["status"],
                (time.perf_counter() - started) * 1000,
            )


def create_app(engine: IntentGuardEngine | None = None, settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    if engine is None:
        if settings.store_kind is StoreKind.POSTGRES and settings.database_url:
            store = SqlStore(settings.database_url)
        else:
            url = "sqlite:///" + settings.sqlite_path if settings.store_kind is StoreKind.SQLITE else "sqlite://"
            Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            store = SqlStore(url)
        engine = IntentGuardEngine(store, settings=settings)

    app = FastAPI(
        title="IntentGuard API",
        version="0.1.0",
        description="Runtime authorization and security control plane for autonomous AI agents.",
    )
    app.state.engine = engine
    app.state.settings = settings
    app.state.rate_limiter = RateLimiter(settings.rate_limit_per_min)
    app.state.stream_tokens = StreamTokenBroker()
    app.include_router(router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "X-API-Key", "Content-Type"],
    )

    logger = logging.getLogger("intentguard.http")

    # Pure ASGI middleware — deliberately NOT @app.middleware("http")
    # (BaseHTTPMiddleware wraps the response body stream, which deadlocks
    # infinite SSE responses). Adds: rate limiting, request IDs, structured
    # access logs (path only — never the query string, so stream tokens and
    # any future query credentials cannot reach logs), security headers.
    app.add_middleware(
        RequestContextMiddleware,
        rate_limiter=app.state.rate_limiter,
        logger=logger,
    )

    @app.exception_handler(IntentGuardError)
    async def domain_error_handler(request: Request, exc: IntentGuardError):
        status = 400
        for error_type, code in _STATUS_BY_ERROR.items():
            if isinstance(exc, error_type):
                status = code
                break
        return JSONResponse(status_code=status, content={"error": exc.code, "message": str(exc)})

    @app.get("/health")
    def health():
        return {"status": "ok", "service": "intentguard", "version": "0.1.0"}

    # Bootstrap: seed the first org + admin key on an empty store, printing
    # the plaintext key exactly once.
    if settings.bootstrap_admin and not engine.store.list_organizations():
        org = engine.create_organization("Primary Organization")
        principal = engine.create_principal(org.org_id, "Administrator")
        _, plaintext = engine.create_api_key(org.org_id, principal.principal_id, "admin", "bootstrap")
        print(
            "\n=== IntentGuard bootstrap ===\n"
            f"Organization: {org.org_id}\n"
            f"Admin API key (shown ONCE — store it now): {plaintext}\n"
            "=============================\n",
            file=sys.stderr,
        )

    # control-plane dashboard (no build step; served statically)
    # app.py = <root>/backend/intentguard/api/app.py → repo root is parents[3]
    frontend_dir = Path(__file__).resolve().parents[3] / "frontend"
    if frontend_dir.exists():
        app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
        # shared design assets for the public landing page
        app.mount("/assets", StaticFiles(directory=str(frontend_dir / "assets")), name="assets")

        landing = frontend_dir / "landing.html"

        @app.get("/", include_in_schema=False)
        def public_landing():
            from fastapi.responses import FileResponse

            response = FileResponse(landing, media_type="text/html")
            response.headers["Cache-Control"] = "public, max-age=300"
            return response

    return app


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    app = create_app(settings=settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
