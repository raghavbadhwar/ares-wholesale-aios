"""Approval-gated WhatsApp Business local contracts."""

from __future__ import annotations

from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_mapping_token

WHATSAPP_BUSINESS_LIMITATION = "Local WhatsApp Business contract only; no Meta API send or production webhook processing occurred."


def prepare_whatsapp_business_message(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    customer_id: str,
    template_name: str,
    body: str,
    requested_by: str,
    dedupe_key: str | None = None,
) -> dict:
    customer = next(item for item in repository.get_customers() if item.id == customer_id)
    key = dedupe_key or f"whatsapp:{stable_mapping_token({'customer_id': customer_id, 'template_name': template_name, 'body': body})}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="send_whatsapp_business_message",
        proposed_action=f"Send WhatsApp template {template_name} to {customer.name}",
        data={
            "customer_id": customer_id,
            "channel": "whatsapp_business",
            "recipient_phone": customer.phone,
            "template_name": template_name,
            "body": body,
            "selected_language": customer.preferred_language,
            "idempotency_key": key,
        },
        reason="Customer-facing WhatsApp messages require owner approval.",
        source="whatsapp_business_contract",
        confidence=1.0,
        dedupe_key=key,
    )
    return {
        "status": "approval_required",
        "approval_id": approval.id,
        "idempotency_key": key,
        "audit": {"requested_by": requested_by, "whatsapp_api_called": False, "limitation": WHATSAPP_BUSINESS_LIMITATION},
    }


def record_whatsapp_delivery_receipt(
    *,
    repository: BusinessRepository,
    client_id: str,
    approval_id: str | None,
    provider_message_id: str,
    recipient_phone: str,
    status: str,
) -> dict:
    receipt = {
        "provider_message_id": provider_message_id,
        "recipient_phone": recipient_phone,
        "delivery_status": status,
        "message_drop": status.lower() in {"failed", "undelivered"},
        "external_whatsapp_business_api_called": False,
        "limitation": WHATSAPP_BUSINESS_LIMITATION,
    }
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_{uuid4().hex[:12]}",
            client_id=client_id,
            approval_id=approval_id,
            action_type="whatsapp_delivery_receipt",
            status="failed" if receipt["message_drop"] else "executed",
            result=receipt,
        )
    )
    return receipt
