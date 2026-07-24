"""Approval resolution — transactionally safe, idempotent-by-conflict."""

from __future__ import annotations

import uuid

from app.db.base import utcnow
from app.db.session import session_scope
from app.domain.enums import ApprovalStatus
from app.domain.errors import ConflictError, NotFoundError
from app.repositories import ApprovalRepository, EventRepository


class ApprovalService:
    def resolve_in_db(self, approval_id: uuid.UUID, outcome: str) -> dict:
        """Resolve an approval and write its event in one transaction.

        Returns the mission id and the new event seq so the caller (on the event
        loop) can wake SSE subscribers and signal the paused orchestrator.
        """
        approved = outcome == "approved"
        with session_scope() as session:
            approvals = ApprovalRepository(session)
            approval = approvals.get(approval_id)
            if approval is None:
                raise NotFoundError("Approval not found", {"approval_id": str(approval_id)})
            if approval.status is not ApprovalStatus.PENDING:
                raise ConflictError(
                    "Approval has already been resolved.",
                    {"approval_id": str(approval_id), "status": approval.status.value},
                )
            approvals.resolve(
                approval,
                ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED,
                utcnow(),
            )
            event_type = "approval.granted" if approved else "approval.rejected"
            message = (
                "Human approved the production deployment."
                if approved
                else "Human rejected the production deployment."
            )
            event = EventRepository(session).append(
                approval.mission_id, event_type, "security", message,
                {"approval_id": str(approval_id)},
            )
            return {"mission_id": approval.mission_id, "seq": event.seq}


approval_service = ApprovalService()
