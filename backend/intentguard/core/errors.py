"""Errors with stable machine-readable codes (never leak internals to agents)."""
from __future__ import annotations


class IntentGuardError(Exception):
    code = "INTENTGUARD_ERROR"

    def __init__(self, message: str = "", *, code: str | None = None) -> None:
        super().__init__(message or self.code)
        if code:
            self.code = code


class ValidationError(IntentGuardError):
    code = "VALIDATION_ERROR"


class NotFoundError(IntentGuardError):
    code = "NOT_FOUND"


class PermissionDeniedError(IntentGuardError):
    code = "PERMISSION_DENIED"


class RateLimitError(IntentGuardError):
    code = "RATE_LIMITED"


class ConflictError(IntentGuardError):
    code = "CONFLICT"
