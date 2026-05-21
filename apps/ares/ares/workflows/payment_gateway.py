"""Local payment gateway contract surfaces."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, Invoice, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.payment_reconciliation import ingest_payment_receipt

LOCAL_PAYMENT_GATEWAY_LIMITATION = (
    "Local payment gateway contract only; no Razorpay, Cashfree, PhonePe, UPI autopay, QR generation, "
    "live webhook, or bank execution was called."
)


def prepare_payment_gateway_link_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    invoice_id: str,
    provider: str,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare an approval-gated local payment-link request contract."""
    invoice = _find_invoice(repository, invoice_id)
    request = {
        "request_id": f"pg_link_{uuid4().hex[:12]}",
        "provider": provider.strip().lower(),
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "amount": round(float(invoice.amount), 2),
        "currency": "INR",
        "supported_methods": ["upi", "card", "netbanking"],
        "webhook_contract": {
            "events": ["payment.captured", "payment.failed"],
            "signature_verification_required": True,
            "reconciliation_required": True,
        },
    }
    audit = _link_audit(requested_by=requested_by, approval_required=True)
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="create_payment_gateway_link",
        proposed_action=f"Review payment link contract for invoice {invoice.invoice_number}",
        data={"request": request, "mode": "local_contract_mock"},
        reason="Payment links affect customer-facing collection and gateway settlement; owner approval is required first.",
        source="payment_gateway",
        confidence=0.84,
        risk_level=RiskLevel.medium,
        dedupe_key=f"payment_gateway_link:{client_id}:{invoice.id}:{request['request_id']}",
    )
    result = {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "request": request,
        "audit": audit,
    }
    _save_log(
        repository,
        client_id=client_id,
        action_type="payment_gateway_link_contract",
        status=result["status"],
        result={
            "request_id": request["request_id"],
            "provider": request["provider"],
            "invoice_id": request["invoice_id"],
            "payment_gateway_api_called": audit["payment_gateway_api_called"],
            "payment_link_created": audit["payment_link_created"],
            "limitation": audit["limitation"],
        },
        approval_id=approval.id,
    )
    return result


def ingest_payment_gateway_webhook_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    provider: str,
    webhook_event: dict[str, Any],
) -> dict[str, Any]:
    """Ingest a local payment gateway webhook-shaped event and reconcile it."""
    payment = ingest_payment_receipt(
        repository=repository,
        approvals=approvals,
        client_id=client_id,
        receipt={
            "party_id": webhook_event.get("customer_id") or webhook_event.get("party_id"),
            "amount": webhook_event.get("amount", 0),
            "received_on": _parse_date(webhook_event.get("paid_on") or webhook_event.get("event_time")),
            "mode": f"{provider.strip().lower()}_upi",
            "reference": webhook_event.get("utr") or webhook_event.get("payment_id"),
            "gateway_event": dict(webhook_event),
        },
    )
    audit = {
        "provider": provider.strip().lower(),
        "live_webhook_received": False,
        "webhook_signature_verified": False,
        "payment_gateway_api_called": False,
        "bank_execution_performed": False,
        "limitation": LOCAL_PAYMENT_GATEWAY_LIMITATION,
    }
    result = {
        "mode": "local_contract_mock",
        "status": payment["status"],
        "event_type": webhook_event.get("event_type"),
        "payment": payment,
        "audit": audit,
    }
    _save_log(
        repository,
        client_id=client_id,
        action_type="payment_gateway_webhook_contract",
        status=result["status"],
        result={
            "provider": audit["provider"],
            "event_type": result["event_type"],
            "payment_id": payment["payment_id"],
            "matched_invoice_id": payment["matched_invoice_id"],
            "live_webhook_received": audit["live_webhook_received"],
            "payment_gateway_api_called": audit["payment_gateway_api_called"],
            "limitation": audit["limitation"],
        },
    )
    return result


def _find_invoice(repository: BusinessRepository, invoice_id: str) -> Invoice:
    for invoice in repository.get_invoices():
        if invoice.id == invoice_id:
            return invoice
    raise KeyError(f"Invoice not found: {invoice_id}")


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip())
    return None


def _link_audit(*, requested_by: str, approval_required: bool) -> dict[str, Any]:
    return {
        "requested_by": requested_by,
        "approval_required": approval_required,
        "payment_gateway_api_called": False,
        "payment_link_created": False,
        "qr_code_generated": False,
        "autopay_setup": False,
        "bank_execution_performed": False,
        "limitation": LOCAL_PAYMENT_GATEWAY_LIMITATION,
    }


def _save_log(
    repository: BusinessRepository,
    *,
    client_id: str,
    action_type: str,
    status: str,
    result: dict[str, Any],
    approval_id: str | None = None,
) -> None:
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_{uuid4().hex[:12]}",
            client_id=client_id,
            approval_id=approval_id,
            action_type=action_type,
            status=status,
            result=result,
        )
    )
