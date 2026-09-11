"""FastAPI application factory."""
from __future__ import annotations

import sys
import time
from collections import defaultdict, deque
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
    """In-memory sliding window per API key (MVP; use Redis in production)."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] > 60:
            hits.popleft()
        if len(hits) >= self.per_minute:
            raise RateLimitError("rate limit exceeded")
        hits.append(now)


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
    app.include_router(router)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "X-API-Key", "Content-Type"],
    )

    @app.middleware("http")
    async def security_and_rate_limit(request: Request, call_next):
        try:
            if request.url.path.startswith("/api/"):
                key = request.headers.get("authorization") or request.headers.get("x-api-key") or "anon"
                app.state.rate_limiter.check(key[:72])
            response = await call_next(request)
        except Exception:
            raise
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        return response

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

    return app


def main() -> None:
    import uvicorn

    settings = Settings.from_env()
    app = create_app(settings=settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


if __name__ == "__main__":
    main()
