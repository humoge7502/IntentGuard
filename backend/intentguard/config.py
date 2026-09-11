"""Runtime configuration, loaded from environment variables.

Deliberately dependency-free (no pydantic-settings): a small typed dataclass
keeps the security core portable and the deployment story explicit.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from intentguard.core.enums import StoreKind


@dataclass(frozen=True)
class Settings:
    store_kind: StoreKind = StoreKind.SQLITE
    sqlite_path: str = "./data/intentguard.db"
    database_url: str = ""
    host: str = "127.0.0.1"
    port: int = 8400
    cors_origins: list[str] = field(default_factory=lambda: ["http://127.0.0.1:8400"])
    rate_limit_per_min: int = 600
    audit_signing_key: str = ""  # base64 Ed25519 private key; empty = hash chain only
    bootstrap_admin: bool = True

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        e = dict(env if env is not None else os.environ)

        def get(name: str, default: str = "") -> str:
            return e.get(name, default)

        store_raw = get("INTENTGUARD_STORE", "sqlite").lower()
        try:
            store_kind = StoreKind(store_raw)
        except ValueError:
            store_kind = StoreKind.SQLITE

        cors = [
            o.strip()
            for o in get("INTENTGUARD_CORS_ORIGINS", "http://127.0.0.1:8400").split(",")
            if o.strip()
        ]
        return cls(
            store_kind=store_kind,
            sqlite_path=get("INTENTGUARD_SQLITE_PATH", "./data/intentguard.db"),
            database_url=get("INTENTGUARD_DATABASE_URL"),
            host=get("INTENTGUARD_HOST", "127.0.0.1"),
            port=int(get("INTENTGUARD_PORT", "8400")),
            cors_origins=cors,
            rate_limit_per_min=int(get("INTENTGUARD_RATE_LIMIT_PER_MIN", "600")),
            audit_signing_key=get("INTENTGUARD_AUDIT_SIGNING_KEY"),
            bootstrap_admin=get("INTENTGUARD_BOOTSTRAP_ADMIN", "1") not in {"0", "false", "no"},
        )
