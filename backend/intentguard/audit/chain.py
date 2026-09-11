"""Tamper-evident audit chain (§15).

Each event's hash binds: previous hash, per-org sequence number, timestamp,
and the canonical payload. Verification recomputes the whole chain.

HONEST SECURITY PROPERTY (also documented in SECURITY_MODEL.md): this makes
history tamper-EVIDENT — any edit or deletion of a stored event breaks the
chain detectably. It is NOT immutable: an attacker with full database write
access can rewrite the entire chain from the fork point. The optional Ed25519
signature (key held outside the database) makes undetected rewriting harder:
signatures from the external key cannot be forged by a DB-only attacker, but
full history replacement with a fresh key remains possible. True immutability
requires external anchoring (WORM storage / periodic hash anchoring), listed
as future work.
"""
from __future__ import annotations

import base64
import threading
import time

from intentguard.core.canonical import canonical_dumps, sha256_hex
from intentguard.core.schemas import AuditEvent, utcnow
from intentguard.storage.store import IntentGuardStore

GENESIS_HASH = "0" * 64


class AuditChain:
    def __init__(self, store: IntentGuardStore, signing_key_b64: str = "") -> None:
        self._store = store
        self._lock = threading.Lock()
        self._key = None
        if signing_key_b64:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

            self._key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(signing_key_b64))

    def append(self, org_id: str, event_type: str, payload: dict) -> AuditEvent:
        """Append one event. Concurrent appenders can read the same head and
        compute the same seq; the (org_id, seq) unique index rejects the loser,
        which retries against the refreshed head instead of failing the
        enforcement path."""
        last_error: Exception | None = None
        for attempt in range(4):
            with self._lock:
                head = self._store.get_audit_head(org_id)
                seq = head.seq + 1 if head else 1
                prev_hash = head.hash if head else GENESIS_HASH
                created_at = utcnow()
                material = f"{prev_hash}|{seq}|{created_at.isoformat()}|{canonical_dumps(payload)}"
                event_hash = sha256_hex(material)
                signature = None
                if self._key is not None:
                    signature = base64.b64encode(self._key.sign(material.encode("utf-8"))).decode("ascii")
                event = AuditEvent(
                    seq=seq,
                    org_id=org_id,
                    event_type=event_type,
                    payload=payload,
                    prev_hash=prev_hash,
                    hash=event_hash,
                    signature=signature,
                    created_at=created_at,
                )
                try:
                    self._store.append_audit_event(event)
                    return event
                except Exception as exc:  # noqa: BLE001 — narrowed below
                    from sqlalchemy.exc import IntegrityError

                    if not isinstance(exc, IntegrityError):
                        raise
                    last_error = exc
            # head moved under us: brief backoff, then re-read and recompute
            time.sleep(0.005 * (attempt + 1))
        raise RuntimeError(f"audit chain append failed after retries for org {org_id}") from last_error

    def verify(self, org_id: str) -> dict:
        events = self._store.list_audit_events(org_id, limit=1_000_000)
        prev_hash = GENESIS_HASH
        for event in events:
            material = f"{prev_hash}|{event.seq}|{event.created_at.isoformat()}|{canonical_dumps(event.payload)}"
            if event.prev_hash != prev_hash or event.hash != sha256_hex(material):
                return {"valid": False, "events": len(events), "broken_at_seq": event.seq}
            if self._key is not None and event.signature is not None:
                try:
                    self._key.public_key().verify(
                        base64.b64decode(event.signature), material.encode("utf-8")
                    )
                except Exception:
                    return {"valid": False, "events": len(events), "broken_at_seq": event.seq}
            prev_hash = event.hash
        return {"valid": True, "events": len(events), "broken_at_seq": None}
