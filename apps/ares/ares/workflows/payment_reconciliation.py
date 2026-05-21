"""Structured receipt reconciliation against open invoices."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Invoice, Payment, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip())
    return None


def _same_party_open_invoices(repository: BusinessRepository, party_id: str | None) -> list[Invoice]:
    if not party_id:
        return []
    return [invoice for invoice in repository.get_outstanding() if invoice.customer_id == party_id]


def _payment_payload(payment: Payment) -> dict:
    return {
        "payment_id": payment.id,
        "party_id": payment.customer_id,
        "amount": payment.amount,
        "status": payment.status,
        "matched_invoice_id": payment.matched_invoice_id,
        "candidate_invoice_ids": payment.candidate_invoice_ids,
        "unapplied_amount": payment.unapplied_amount,
        "audit_note": payment.audit_note,
    }


def _mark_invoice_paid(repository: BusinessRepository, invoice: Invoice) -> None:
    repository.upsert_invoice(invoice.model_copy(update={"status": "paid"}))


def _save_payment(repository: BusinessRepository, payment: Payment) -> dict:
    saved = repository.upsert_payment(payment)
    return _payment_payload(saved)


def ingest_payment_receipt(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    receipt: dict[str, Any],
) -> dict:
    """Ingest one structured UPI/bank receipt and reconcile deterministic matches.

    This is a local contract-level primitive, not a live UPI gateway webhook.
    """
    party_id = receipt.get("party_id") or receipt.get("customer_id")
    amount = float(receipt.get("amount", 0))
    payment_date = _parse_date(receipt.get("received_on") or receipt.get("date")) or date.today()
    mode = receipt.get("mode") or "upi"
    reference = receipt.get("reference") or receipt.get("utr")
    open_invoices = _same_party_open_invoices(repository, party_id)
    exact_matches = [invoice for invoice in open_invoices if float(invoice.amount) == amount]

    payment = Payment(
        id=f"pay_{uuid4().hex[:12]}",
        customer_id=party_id,
        amount=amount,
        date=payment_date,
        mode=mode,
        reference=reference,
        raw_source=dict(receipt),
        confidence=0.95,
    )

    if len(exact_matches) == 1:
        invoice = exact_matches[0]
        _mark_invoice_paid(repository, invoice)
        return _save_payment(
            repository,
            payment.model_copy(
                update={
                    "status": "reconciled",
                    "matched_invoice_id": invoice.id,
                    "candidate_invoice_ids": [invoice.id],
                    "audit_note": "Exact party and amount match reconciled locally.",
                }
            ),
        )

    if len(exact_matches) > 1:
        candidate_ids = [invoice.id for invoice in exact_matches]
        review_payment = payment.model_copy(
            update={
                "status": "needs_review",
                "candidate_invoice_ids": candidate_ids,
                "audit_note": "Multiple open invoices matched party_id and amount.",
                "confidence": 0.6,
            }
        )
        saved_payload = _save_payment(repository, review_payment)
        approvals.create_approval_request(
            client_id=client_id,
            action_type="review_payment_reconciliation",
            proposed_action=f"Review payment reconciliation for {party_id}",
            data={
                "payment_id": review_payment.id,
                "party_id": party_id,
                "amount": amount,
                "reference": reference,
                "candidate_invoice_ids": candidate_ids,
            },
            reason="Multiple open invoices match this receipt; owner/accountant must choose the ledger posting.",
            source="payment_reconciliation",
            confidence=review_payment.confidence,
            risk_level=RiskLevel.high,
            dedupe_key=f"payment_reconciliation:{reference or review_payment.id}",
        )
        return saved_payload

    if len(open_invoices) == 1 and amount > float(open_invoices[0].amount):
        invoice = open_invoices[0]
        unapplied_amount = round(amount - float(invoice.amount), 2)
        _mark_invoice_paid(repository, invoice)
        return _save_payment(
            repository,
            payment.model_copy(
                update={
                    "status": "partially_reconciled",
                    "matched_invoice_id": invoice.id,
                    "candidate_invoice_ids": [invoice.id],
                    "unapplied_amount": unapplied_amount,
                    "audit_note": "Single party invoice paid; excess kept as unapplied balance.",
                }
            ),
        )

    audit_note = "No open invoice matched party_id and amount."
    if open_invoices:
        audit_note = "Open invoices found for party_id, but no amount match was deterministic."
    return _save_payment(
        repository,
        payment.model_copy(
            update={
                "status": "unreconciled",
                "candidate_invoice_ids": [invoice.id for invoice in open_invoices],
                "audit_note": audit_note,
                "confidence": 0.4,
            }
        ),
    )
