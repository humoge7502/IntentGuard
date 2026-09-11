from __future__ import annotations

import uuid


def new_id(prefix: str) -> str:
    """Prefixed opaque identifier, e.g. ``int_9f2c...``."""
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


PREFIXES = {
    "org": "org",
    "principal": "usr",
    "agent": "agt",
    "session": "ses",
    "intent": "int",
    "capability": "cap",
    "action": "act",
    "decision": "dec",
    "approval": "apr",
    "api_key": "key",
    "benchmark": "bm_",
    "policy": "pol",
}
