"""Domain enums. Strings are stable wire/audit identifiers — never renumber."""
from __future__ import annotations

from enum import Enum


class Decision(str, Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"


class SideEffectClass(str, Enum):
    """Impact taxonomy (§68). Higher-impact classes require stronger authorization."""

    READ = "READ"
    SEARCH = "SEARCH"
    ANALYZE = "ANALYZE"
    WRITE = "WRITE"
    MODIFY = "MODIFY"
    DELETE = "DELETE"
    PURCHASE = "PURCHASE"
    TRANSFER = "TRANSFER"
    SEND = "SEND"
    EXECUTE = "EXECUTE"


# Operations in these classes are externally consequential and always require
# an explicit capability scope plus satisfied constraints.
HIGH_IMPACT_CLASSES = frozenset(
    {
        SideEffectClass.DELETE,
        SideEffectClass.PURCHASE,
        SideEffectClass.TRANSFER,
        SideEffectClass.SEND,
        SideEffectClass.EXECUTE,
    }
)


class PolicyLayer(str, Enum):
    """Policy hierarchy (§69). Resolution takes minima of limits and honors all
    denies — a more permissive layer can never widen a stricter one."""

    ORGANIZATION = "organization"
    USER = "user"
    AGENT = "agent"
    INTENT = "intent"


class CheckStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIPPED = "skipped"


class RiskBand(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class CapabilityStatus(str, Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    DENIED = "denied"
    EXPIRED = "expired"
    CONSUMED = "consumed"


class StoreKind(str, Enum):
    MEMORY = "memory"
    SQLITE = "sqlite"
    POSTGRES = "postgres"
