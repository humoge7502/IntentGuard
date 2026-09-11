"""Canonical serialization used for digests, replay detection, and the audit chain.

Two byte-for-byte identical inputs must always produce the same canonical form,
so hashes are stable across processes and platforms.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any


def _json_default(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (set, frozenset)):
        return sorted(value, key=repr)
    if isinstance(value, tuple):
        return list(value)
    raise TypeError(f"not JSON serializable: {type(value)!r}")


def canonical_dumps(value: Any) -> str:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8 friendly."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_of(value: Any) -> str:
    """Stable SHA-256 digest of any JSON-serializable structure."""
    return sha256_hex(canonical_dumps(value))
