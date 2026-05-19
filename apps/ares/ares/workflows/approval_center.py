"""Approval center workflow facade."""

from __future__ import annotations

from apps.ares.ares.approvals.formatter import format_approval_list
from apps.ares.ares.approvals.service import ApprovalService


def list_pending(approvals: ApprovalService) -> dict:
    pending = approvals.list_pending_requests()
    return {
        "count": len(pending),
        "approvals": [approval.model_dump(mode="json") for approval in pending],
        "message": format_approval_list(pending),
    }


def approve_selected(approvals: ApprovalService, approval_id: str, *, decided_by: str) -> dict:
    approval = approvals.approve_request(approval_id, decided_by=decided_by)
    return approval.model_dump(mode="json")


def reject_selected(approvals: ApprovalService, approval_id: str, *, decided_by: str) -> dict:
    approval = approvals.reject_request(approval_id, decided_by=decided_by)
    return approval.model_dump(mode="json")

