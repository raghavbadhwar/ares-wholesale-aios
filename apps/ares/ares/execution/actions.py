"""Execute approved Ares actions and write an audit trail."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from apps.ares.ares.data.models import ActionExecutionLog, ApprovalStatus
from apps.ares.ares.data.repository import BusinessRepository


class MessageSender:
    def send_message(self, *, recipient: str, body: str) -> dict:
        raise NotImplementedError


@dataclass
class InMemoryMessageSender(MessageSender):
    sent_messages: list[dict] = field(default_factory=list)

    def send_message(self, *, recipient: str, body: str) -> dict:
        payload = {"recipient": recipient, "body": body}
        self.sent_messages.append(payload)
        return {"status": "sent", **payload}


class DryRunMessageSender(MessageSender):
    def send_message(self, *, recipient: str, body: str) -> dict:
        return {"status": "dry_run", "recipient": recipient, "body": body}


class ActionExecutor:
    def __init__(self, repository: BusinessRepository, *, message_sender: MessageSender | None = None) -> None:
        self.repository = repository
        self.message_sender = message_sender or DryRunMessageSender()

    def execute_approved(self, approval_id: str) -> ActionExecutionLog:
        approval = self.repository.find_approval(approval_id)
        if approval is None:
            raise KeyError(f"Approval not found: {approval_id}")
        if approval.status != ApprovalStatus.approved:
            raise PermissionError(f"Approval is not approved: {approval_id}")
        try:
            result = self._execute_action(approval.type, approval.data)
            log = ActionExecutionLog(
                id=f"act_{uuid4().hex[:12]}",
                client_id=approval.client_id,
                approval_id=approval.id,
                action_type=approval.type,
                status="executed",
                result=result,
            )
        except Exception as exc:
            log = ActionExecutionLog(
                id=f"act_{uuid4().hex[:12]}",
                client_id=approval.client_id,
                approval_id=approval.id,
                action_type=approval.type,
                status="failed",
                error=str(exc),
            )
        return self.repository.save_action_log(log)

    def _execute_action(self, action_type: str, data: dict) -> dict:
        if action_type in {"send_customer_message", "send_supplier_message"}:
            recipient = str(data.get("customer") or data.get("supplier") or data.get("recipient") or "")
            body = str(data.get("draft") or data.get("message") or "")
            if not recipient or not body:
                raise ValueError("message action requires recipient/customer and draft/message")
            return self.message_sender.send_message(recipient=recipient, body=body)
        if action_type == "update_order_status":
            order_id = str(data["order_id"])
            status = str(data["status"])
            order = self.repository.update_order_status(order_id, status)
            return {"status": "updated", "order_id": order.id, "order_status": order.status}
        return {"status": "logged_only", "action_type": action_type, "data": data}
