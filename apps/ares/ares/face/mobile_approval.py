"""Mobile-first approval adapter for Telegram/WhatsApp-style messages."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.execution.actions import ActionExecutor
from apps.ares.ares.face.owner_chat import handle_owner_reply

_APPROVE = {"approve", "approved", "yes", "y", "ok", "haan", "ha"}
_REJECT = {"reject", "rejected", "no", "n", "nah"}
_LATER = {"later", "asklater", "ask_later", "baad", "baadme", "hold"}


def parse_mobile_reply(text: str) -> dict:
    parts = text.strip().split(maxsplit=2)
    if not parts:
        return {"decision": "ask_later", "approval_id": "", "edit_text": ""}
    command = parts[0].strip().lower()
    approval_id = parts[1].strip().lower() if len(parts) > 1 else ""
    edit_text = parts[2].strip() if len(parts) > 2 else ""
    if command in _APPROVE:
        decision = "approve"
    elif command in _REJECT:
        decision = "reject"
    elif command == "edit":
        decision = "edit"
    elif command in _LATER:
        decision = "ask_later"
    else:
        decision = "ask_later"
    return {"decision": decision, "approval_id": approval_id, "edit_text": edit_text}


class MobileApprovalAdapter:
    def __init__(self, repository: BusinessRepository, approvals: ApprovalService) -> None:
        self.repository = repository
        self.approvals = approvals

    def render_pending_prompt(self) -> str:
        pending = self.approvals.list_pending_requests()
        if not pending:
            return "No approvals pending."
        lines = ["🔐 Ares approvals pending:"]
        for idx, approval in enumerate(pending, start=1):
            affected = approval.data.get("customer") or approval.data.get("supplier") or approval.data.get("order_id") or "business record"
            lines.extend(
                [
                    f"{idx}) {approval.proposed_action}",
                    f"   For: {affected}",
                    f"   Risk: {approval.risk_level}",
                    f"   Reply: approve {approval.id} / reject {approval.id} / edit {approval.id} <text> / later {approval.id}",
                ]
            )
        return "\n".join(lines)

    def handle_reply(self, text: str, *, decided_by: str) -> dict:
        parsed = parse_mobile_reply(text)
        approval_id = parsed["approval_id"]
        if not approval_id:
            return {"decision": "ask_later", "message": "Please include approval id, e.g. approve appr_xxx"}
        if parsed["decision"] == "approve":
            reply = "approve"
        elif parsed["decision"] == "reject":
            reply = "reject"
        elif parsed["decision"] == "edit":
            reply = f"edit {parsed['edit_text']}"
        else:
            reply = "later"
        return handle_owner_reply(
            reply,
            approvals=self.approvals,
            executor=ActionExecutor(self.repository),
            approval_id=approval_id,
            decided_by=decided_by,
        )
