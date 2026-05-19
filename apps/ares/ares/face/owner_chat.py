"""Owner-facing chat approval helpers."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ApprovalRequest
from apps.ares.ares.execution.actions import ActionExecutor


def render_owner_approval_prompt(approval: ApprovalRequest) -> str:
    affected = approval.data.get("customer") or approval.data.get("supplier") or approval.data.get("order_id") or "business record"
    return (
        f"Approval needed: {approval.proposed_action}\n"
        f"Type: {approval.type}\n"
        f"Reason: {approval.reason}\n"
        f"Affected: {affected}\n"
        "Options: Approve / Edit / Reject / Ask later"
    )


def handle_owner_reply(
    text: str,
    *,
    approvals: ApprovalService,
    executor: ActionExecutor,
    approval_id: str,
    decided_by: str,
) -> dict:
    normalized = text.strip().lower()
    if normalized in {"approve", "approved", "yes", "y", "ok", "haan", "ha"}:
        approval = approvals.approve_request(approval_id, decided_by=decided_by)
        execution = executor.execute_approved(approval.id)
        return {"decision": "approved", "approval": approval.model_dump(mode="json"), "execution": execution.model_dump(mode="json")}
    if normalized in {"reject", "rejected", "no", "n", "nah", "mat karo"}:
        approval = approvals.reject_request(approval_id, decided_by=decided_by)
        return {"decision": "rejected", "approval": approval.model_dump(mode="json")}
    if normalized.startswith("edit "):
        approval = approvals.edit_request(approval_id, decided_by=decided_by, data={"owner_edit": text[5:].strip()})
        return {"decision": "edited", "approval": approval.model_dump(mode="json")}
    return {"decision": "ask_later", "message": "Approval kept pending."}
