"""Contract-only WhatsApp Business execution surface."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, Customer, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.regional_language import SUPPORTED_LANGUAGES

WHATSAPP_BUSINESS_LIMITATION = (
    "Contract-only WhatsApp Business surface; no Meta/WhatsApp production API, webhook, or template registry was called."
)


def _customer_by_id(repository: BusinessRepository, customer_id: str) -> Customer:
    for customer in repository.get_customers():
        if customer.id == customer_id:
            return customer
    raise KeyError(f"Customer not found: {customer_id}")


def _selected_language(customer: Customer) -> str:
    language = customer.preferred_language.strip().lower().replace("-", "_")
    if language in {"english", "hindi", "hinglish"}:
        return "english_hinglish"
    if language in SUPPORTED_LANGUAGES:
        return language
    return "english_hinglish"


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
) -> dict[str, Any]:
    """Draft a WhatsApp Business outbound action for owner approval."""
    customer = _customer_by_id(repository, customer_id)
    if not customer.phone:
        raise ValueError(f"Customer has no phone number: {customer_id}")
    idempotency_key = dedupe_key or f"waba:{client_id}:{customer_id}:{template_name}:{uuid4().hex[:12]}"
    selected_language = _selected_language(customer)
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="send_whatsapp_business_message",
        proposed_action=f"Send WhatsApp Business template '{template_name}' to {customer.name}",
        data={
            "channel": "whatsapp_business",
            "customer_id": customer.id,
            "recipient": customer.name,
            "recipient_phone": customer.phone,
            "template_name": template_name,
            "body": body,
            "selected_language": selected_language,
            "idempotency_key": idempotency_key,
            "mode": "contract_only_mock",
        },
        reason="WhatsApp Business outbound messages are customer-facing and must be owner-approved before dispatch.",
        source="whatsapp_business",
        confidence=0.9,
        risk_level=RiskLevel.medium,
        dedupe_key=idempotency_key,
    )
    return {
        "mode": "contract_only_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "customer_id": customer.id,
        "recipient_phone": customer.phone,
        "template_name": template_name,
        "selected_language": selected_language,
        "idempotency_key": idempotency_key,
        "audit": {
            "requested_by": requested_by,
            "approval_required": True,
            "external_whatsapp_business_api_called": False,
            "limitation": WHATSAPP_BUSINESS_LIMITATION,
        },
    }


def record_whatsapp_delivery_receipt(
    *,
    repository: BusinessRepository,
    client_id: str,
    approval_id: str | None,
    provider_message_id: str,
    recipient_phone: str,
    status: str,
) -> dict[str, Any]:
    """Record a local delivery receipt or drop signal from a mocked WhatsApp provider."""
    normalized_status = status.strip().lower()
    message_drop = normalized_status in {"failed", "undelivered", "dropped", "expired"}
    result = {
        "channel": "whatsapp_business",
        "provider_message_id": provider_message_id,
        "recipient_phone": recipient_phone,
        "delivery_status": normalized_status,
        "message_drop": message_drop,
        "external_whatsapp_business_api_called": False,
        "limitation": WHATSAPP_BUSINESS_LIMITATION,
    }
    log = ActionExecutionLog(
        id=f"act_{uuid4().hex[:12]}",
        client_id=client_id,
        approval_id=approval_id,
        action_type="whatsapp_delivery_receipt",
        status="failed" if message_drop else "executed",
        result=result,
    )
    repository.save_action_log(log)
    return result
