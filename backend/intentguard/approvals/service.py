"""Human approval / escalation (§8).

An approval is bound to ONE action digest, is time-limited, single-use, and
records who granted it. It is never a generic bypass: the digest covers
session, tool, operation, and full parameters, so a grant cannot be reused
for a different action.
"""
from __future__ import annotations

from datetime import timedelta

from intentguard.audit.chain import AuditChain
from intentguard.core.enums import ApprovalStatus
from intentguard.core.errors import ConflictError, NotFoundError
from intentguard.core.schemas import ApprovalRequest, utcnow
from intentguard.storage.store import IntentGuardStore

DEFAULT_TTL_SECONDS = 900  # 15 minutes


class ApprovalService:
    def __init__(self, store: IntentGuardStore, audit: AuditChain) -> None:
        self._store = store
        self._audit = audit

    def request(
        self,
        org_id: str,
        session_id: str,
        intent_id: str,
        action_digest: str,
        action_summary: dict,
        reasons: list[str],
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> ApprovalRequest:
        # Idempotent: re-evaluating the same action must not spawn duplicate
        # pending requests — one open request per (session, digest).
        for existing in self._store.list_approvals(org_id, ApprovalStatus.PENDING):
            if existing.session_id == session_id and existing.action_digest == action_digest:
                if existing.expires_at is not None and existing.expires_at > utcnow():
                    return existing
        approval = ApprovalRequest(
            org_id=org_id,
            session_id=session_id,
            intent_id=intent_id,
            action_digest=action_digest,
            action_summary=action_summary,
            reasons=reasons,
            status=ApprovalStatus.PENDING,
            requested_at=utcnow(),
            expires_at=utcnow() + timedelta(seconds=ttl_seconds),
        )
        self._store.save_approval(approval)
        self._audit.append(
            org_id,
            "approval.requested",
            {"approval_id": approval.approval_id, "session_id": session_id,
             "action_digest": action_digest, "reasons": reasons},
        )
        return approval

    def _resolve(self, org_id: str, approval_id: str, approver: str, new_status: ApprovalStatus) -> ApprovalRequest:
        approval = self._store.get_approval(org_id, approval_id)
        if approval is None:
            raise NotFoundError(f"approval not found: {approval_id}")
        now = utcnow()
        if approval.status != ApprovalStatus.PENDING:
            raise ConflictError(f"approval is already {approval.status.value}")
        if approval.expires_at is not None and approval.expires_at < now:
            approval.status = ApprovalStatus.EXPIRED
            self._store.save_approval(approval)
            raise ConflictError("approval request has expired")
        approval.status = new_status
        approval.granted_by = approver
        approval.resolved_at = now
        self._store.save_approval(approval)
        self._audit.append(
            org_id,
            f"approval.{'granted' if new_status == ApprovalStatus.GRANTED else 'denied'}",
            {"approval_id": approval_id, "approver": approver, "action_digest": approval.action_digest},
        )
        return approval

    def grant(self, org_id: str, approval_id: str, approver: str) -> ApprovalRequest:
        return self._resolve(org_id, approval_id, approver, ApprovalStatus.GRANTED)

    def deny(self, org_id: str, approval_id: str, approver: str) -> ApprovalRequest:
        return self._resolve(org_id, approval_id, approver, ApprovalStatus.DENIED)

    def consume_if_valid(self, org_id: str, session_id: str, action_digest: str) -> ApprovalRequest | None:
        """Atomically consume a granted approval for this exact digest."""
        approval = self._store.find_granted_for_digest(org_id, session_id, action_digest)
        if approval is None:
            return None
        now = utcnow()
        if approval.expires_at is not None and approval.expires_at < now:
            approval.status = ApprovalStatus.EXPIRED
            self._store.save_approval(approval)
            return None
        approval.status = ApprovalStatus.CONSUMED
        approval.resolved_at = now
        self._store.save_approval(approval)
        self._audit.append(
            org_id,
            "approval.consumed",
            {"approval_id": approval.approval_id, "action_digest": action_digest},
        )
        return approval
