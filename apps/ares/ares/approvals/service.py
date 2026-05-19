"""Approval-first guardrails for sensitive Ares actions."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

try:
    from apps.ares.ares.data.models import ApprovalRequest, ApprovalStatus, RiskLevel
    from apps.ares.ares.data.repository import BusinessRepository
except ModuleNotFoundError:
    class ApprovalStatus(str, Enum):
        pending = "pending"
        approved = "approved"
        rejected = "rejected"
        edited = "edited"


    class RiskLevel(str, Enum):
        low = "low"
        medium = "medium"
        high = "high"


    @dataclass(frozen=True)
    class ApprovalRequest:
        id: str
        type: str
        client_id: str
        proposed_action: str
        data: dict[str, Any]
        reason: str
        source: str
        confidence: float
        risk_level: RiskLevel = RiskLevel.medium
        dedupe_key: str | None = None
        status: ApprovalStatus = ApprovalStatus.pending
        decided_by: str | None = None
        decided_at: datetime | None = None

        def model_copy(self, *, update: dict[str, Any] | None = None) -> "ApprovalRequest":
            return replace(self, **(update or {}))


    @runtime_checkable
    class BusinessRepository(Protocol):
        def find_pending_approval(
            self,
            *,
            client_id: str,
            action_type: str,
            dedupe_key: str,
        ) -> ApprovalRequest | None: ...

        def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest: ...

        def update_approval(self, approval: ApprovalRequest) -> ApprovalRequest: ...

        def list_pending_approvals(self) -> list[ApprovalRequest]: ...


DEFAULT_APPROVAL_REQUIRED_ACTIONS = {
    "confirm_unclear_order",
    "add_order_to_dispatch_queue",
    "update_order_status",
    "send_customer_message",
    "send_supplier_message",
    "mark_payment_received",
    "update_invoice_status",
    "modify_ledger",
    "block_dispatch",
    "approve_credit_extension",
    "change_credit_limit",
    "place_purchase_order",
    "activate_recurring_workflow",
    "save_sensitive_business_rule",
    "save_sensitive_memory",
}


class ApprovalService:
    def __init__(
        self,
        repository: BusinessRepository,
        *,
        required_actions: set[str] | None = None,
    ) -> None:
        self.repository = repository
        self.required_actions = required_actions or DEFAULT_APPROVAL_REQUIRED_ACTIONS

    def requires_approval(self, action_type: str, *, confidence: float = 1.0) -> bool:
        if action_type in self.required_actions:
            return True
        return confidence < 0.75

    def create_approval_request(
        self,
        *,
        client_id: str,
        action_type: str,
        proposed_action: str,
        data: dict,
        reason: str,
        source: str,
        confidence: float,
        risk_level: RiskLevel = RiskLevel.medium,
        dedupe_key: str | None = None,
    ) -> ApprovalRequest:
        if dedupe_key:
            existing = self.repository.find_pending_approval(
                client_id=client_id,
                action_type=action_type,
                dedupe_key=dedupe_key,
            )
            if existing is not None:
                return existing
        approval = ApprovalRequest(
            id=f"appr_{uuid4().hex[:12]}",
            type=action_type,
            client_id=client_id,
            proposed_action=proposed_action,
            data=data,
            reason=reason,
            source=source,
            confidence=confidence,
            risk_level=risk_level,
            dedupe_key=dedupe_key,
        )
        return self.repository.create_approval(approval)

    def approve_request(self, approval_id: str, *, decided_by: str) -> ApprovalRequest:
        return self._decide(approval_id, ApprovalStatus.approved, decided_by=decided_by)

    def reject_request(self, approval_id: str, *, decided_by: str) -> ApprovalRequest:
        return self._decide(approval_id, ApprovalStatus.rejected, decided_by=decided_by)

    def edit_request(self, approval_id: str, *, decided_by: str, data: dict) -> ApprovalRequest:
        approval = self._get_pending(approval_id)
        updated = approval.model_copy(
            update={
                "status": ApprovalStatus.edited,
                "data": {**approval.data, **data},
                "decided_by": decided_by,
                "decided_at": datetime.now(timezone.utc),
            }
        )
        return self.repository.update_approval(updated)

    def list_pending_requests(self) -> list[ApprovalRequest]:
        return self.repository.list_pending_approvals()

    def _decide(
        self,
        approval_id: str,
        status: ApprovalStatus,
        *,
        decided_by: str,
    ) -> ApprovalRequest:
        approval = self._get_pending(approval_id)
        updated = approval.model_copy(
            update={
                "status": status,
                "decided_by": decided_by,
                "decided_at": datetime.now(timezone.utc),
            }
        )
        return self.repository.update_approval(updated)

    def _get_pending(self, approval_id: str) -> ApprovalRequest:
        for approval in self.repository.list_pending_approvals():
            if approval.id == approval_id:
                return approval
        raise KeyError(f"Pending approval not found: {approval_id}")


def requires_approval(action_type: str, *, confidence: float = 1.0) -> bool:
    return action_type in DEFAULT_APPROVAL_REQUIRED_ACTIONS or confidence < 0.75

