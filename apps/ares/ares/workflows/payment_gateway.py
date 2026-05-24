"""Approval-gated local payment gateway contracts."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, Payment
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_contract_token

LOCAL_PAYMENT_GATEWAY_LIMITATION = "Local payment gateway contract only; no provider API call or bank execution was performed."


def prepare_payment_gateway_link_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    invoice_id: str,
    provider: str,
    requested_by: str,
) -> dict:
    invoice = next(item for item in repository.get_invoices() if item.id == invoice_id)
    request_id = f"payreq_{stable_contract_token(client_id, invoice_id, provider)}"
    dedupe_key = f"payment_gateway:{request_id}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="create_payment_gateway_link",
        proposed_action=f"Create {provider} payment link for invoice {invoice.invoice_number}",
        data={"invoice_id": invoice_id, "provider": provider, "request_id": request_id, "amount": invoice.amount},
        reason="Payment links are customer-facing and must be owner approved.",
        source="payment_gateway_contract",
        confidence=1.0,
        dedupe_key=dedupe_key,
    )
    return {
        "status": "approval_required",
        "approval_id": approval.id,
        "idempotency_key": dedupe_key,
        "request": {"request_id": request_id, "invoice_id": invoice_id, "provider": provider},
        "audit": {"requested_by": requested_by, "provider_api_called": False, "limitation": LOCAL_PAYMENT_GATEWAY_LIMITATION},
    }


def ingest_payment_gateway_webhook_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    provider: str,
    webhook_event: dict,
) -> dict:
    event_type = str(webhook_event.get("event_type") or "").lower()
    signature_status = str(webhook_event.get("signature_verification_status") or "")
    signature_verified = signature_status in {"verified", "verified_contract_fixture"}
    payment_id = str(webhook_event.get("payment_id") or "")

    existing = repository.find_payment_by_external_event_id(payment_id) if payment_id else None
    if existing is not None:
        result = {
            "status": "duplicate_ignored",
            "payment": _payment_payload(existing),
            "audit": _audit(provider=provider, signature_verified=False, duplicate=True, payment_created=False),
        }
        _log(repository, client_id, result["status"], result)
        return result

    if event_type not in {"payment.captured", "payment.success", "checkout.order.completed"}:
        result = {
            "status": "ignored_non_success_event",
            "payment": None,
            "audit": _audit(provider=provider, signature_verified=signature_verified, duplicate=False, payment_created=False),
        }
        _log(repository, client_id, result["status"], result)
        return result

    invoice_id = webhook_event.get("invoice_id")
    matched_invoice = None
    for invoice in repository.get_invoices():
        if invoice_id and invoice.id == invoice_id:
            matched_invoice = invoice
            break
        if not invoice_id and abs(float(invoice.amount) - float(webhook_event.get("amount") or 0)) < 0.01:
            matched_invoice = invoice
            break

    if not signature_verified:
        payment = Payment(
            id=payment_id or f"pay_{stable_contract_token(client_id, provider, webhook_event)}",
            client_id=client_id,
            customer_id=webhook_event.get("customer_id"),
            amount=float(webhook_event.get("amount") or 0),
            reference=webhook_event.get("utr"),
            status="blocked_unverified_signature",
            provider=provider,
            external_event_id=payment_id or None,
            source_event_type=event_type,
            signature_verification_status="not_verified_contract_mock",
            raw_source={"gateway_event": webhook_event},
        )
        repository.upsert_payment(payment)
        result = {
            "status": "blocked_unverified_signature",
            "payment": _payment_payload(payment),
            "audit": _audit(provider=provider, signature_verified=False, duplicate=False, payment_created=True),
        }
        _log(repository, client_id, result["status"], result)
        return result

    payment = Payment(
        id=payment_id or f"pay_{stable_contract_token(client_id, provider, webhook_event)}",
        client_id=client_id,
        customer_id=webhook_event.get("customer_id") or (matched_invoice.customer_id if matched_invoice else None),
        amount=float(webhook_event.get("amount") or 0),
        date=webhook_event.get("paid_on"),
        mode=provider,
        reference=webhook_event.get("utr"),
        matched_invoice_id=matched_invoice.id if matched_invoice else None,
        status="reconciled",
        provider=provider,
        external_event_id=payment_id or None,
        source_event_type=event_type,
        signature_verification_status="verified_contract_fixture",
        raw_source={"gateway_event": webhook_event},
    )
    saved = repository.upsert_payment(payment)
    result = {
        "status": "reconciled",
        "payment": _payment_payload(saved),
        "audit": _audit(provider=provider, signature_verified=True, duplicate=False, payment_created=True),
    }
    _log(repository, client_id, result["status"], result)
    return result


def _payment_payload(payment: Payment) -> dict:
    payload = payment.model_dump(mode="json")
    payload["payment_id"] = payment.id
    return payload


def _audit(*, provider: str, signature_verified: bool, duplicate: bool, payment_created: bool) -> dict:
    return {
        "provider": provider,
        "live_webhook_received": False,
        "webhook_signature_verified": signature_verified,
        "payment_gateway_api_called": False,
        "bank_execution_performed": False,
        "duplicate_event_ignored": duplicate,
        "payment_record_created": payment_created,
        "limitation": LOCAL_PAYMENT_GATEWAY_LIMITATION,
    }


def _log(repository: BusinessRepository, client_id: str, status: str, result: dict) -> None:
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_payment_{stable_contract_token(client_id, status, result)}",
            client_id=client_id,
            action_type="payment_gateway_webhook_contract",
            status=status,
            result=result,
        )
    )
