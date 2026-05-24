"""Local supplier payment reconciliation workflow."""

from __future__ import annotations

from datetime import date
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import LedgerEntry, SupplierPayment, SupplierPaymentAllocation
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_SUPPLIER_PAYMENT_LIMITATION = "Local supplier payment reconciliation only; no bank execution or provider mutation was performed."


def _invoice_total(invoice) -> float:
    return float(invoice.taxable_value or 0) + float(invoice.tax_amount or 0)


def _parse_date(value) -> date | None:
    if isinstance(value, date):
        return value
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def ingest_supplier_payment_receipt(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    receipt: dict,
) -> dict:
    external_event_id = receipt.get("external_event_id")
    if external_event_id:
        existing = repository.find_supplier_payment_by_external_event_id(str(external_event_id))
        if existing is not None:
            return {
                "status": existing.status,
                "supplier_payment_id": existing.id,
                "supplier_payment": {**existing.model_dump(mode="json"), "supplier_payment_id": existing.id},
                "external_event_id": existing.external_event_id,
                "matched_purchase_invoice_id": existing.matched_purchase_invoice_id,
            }

    supplier_id = str(receipt.get("supplier_id") or "")
    amount = float(receipt.get("amount") or 0)
    candidate_invoices = [
        invoice
        for invoice in repository.get_purchase_invoices()
        if invoice.supplier_id == supplier_id and repository.effective_purchase_invoice_projection(invoice)["status"] not in {"paid", "cancelled"}
    ]
    exact_matches = [invoice for invoice in candidate_invoices if abs(_invoice_total(invoice) - amount) < 0.01]
    explicit_invoice = str(receipt.get("purchase_invoice_id") or "")
    if explicit_invoice:
        exact_matches = [invoice for invoice in candidate_invoices if invoice.id == explicit_invoice] or exact_matches

    has_external_provider = bool(receipt.get("provider") or external_event_id or receipt.get("source_event_type"))
    signature_status = str(receipt.get("signature_verification_status") or "")
    if has_external_provider and signature_status not in {"verified", "verified_contract_fixture"}:
        payment = SupplierPayment(
            id=f"sup_pay_{uuid4().hex[:12]}",
            client_id=client_id,
            supplier_id=supplier_id,
            amount=amount,
            date=_parse_date(receipt.get("paid_on") or receipt.get("date")),
            mode=receipt.get("mode"),
            reference=receipt.get("reference"),
            status="blocked_unverified_signature",
            provider=receipt.get("provider"),
            external_event_id=external_event_id,
            source_event_type=receipt.get("source_event_type"),
            signature_verification_status="not_verified_contract_mock",
        )
        repository.upsert_supplier_payment(payment)
        return {
            "status": payment.status,
            "supplier_payment_id": payment.id,
            "supplier_payment": {**payment.model_dump(mode="json"), "supplier_payment_id": payment.id},
            "matched_purchase_invoice_id": None,
            "candidate_purchase_invoice_ids": [invoice.id for invoice in candidate_invoices],
        }

    if len(exact_matches) == 1 or (not exact_matches and len(candidate_invoices) == 1):
        invoice = exact_matches[0] if exact_matches else candidate_invoices[0]
        total = _invoice_total(invoice)
        payment = SupplierPayment(
            id=f"sup_pay_{uuid4().hex[:12]}",
            client_id=client_id,
            supplier_id=supplier_id,
            amount=amount,
            date=_parse_date(receipt.get("paid_on") or receipt.get("date")),
            mode=receipt.get("mode"),
            reference=receipt.get("reference"),
            matched_purchase_invoice_id=invoice.id,
            unapplied_amount=max(0.0, amount - total),
            status="reconciled" if amount <= total else "partially_reconciled",
            provider=receipt.get("provider"),
            external_event_id=external_event_id,
            source_event_type=receipt.get("source_event_type"),
            signature_verification_status=signature_status or "verified_contract_fixture",
        )
        saved = repository.upsert_supplier_payment(payment)
        allocation = SupplierPaymentAllocation(
            id=f"sup_alloc_{uuid4().hex[:12]}",
            supplier_payment_id=saved.id,
            purchase_invoice_id=invoice.id,
            amount=min(amount, total),
            status="posted",
        )
        repository.upsert_supplier_payment_allocation(allocation)
        repository.upsert_ledger_entry(
            LedgerEntry(
                id=f"led_supplier_payment_{allocation.id}",
                entry_type="supplier_payment_allocation",
                source_type="supplier_payment",
                source_id=saved.id,
                amount=allocation.amount,
                debit_account="Accounts Payable",
                credit_account="Bank",
            )
        )
        repository.ledger_entries.pop(f"led_purchase_{invoice.id}_base", None)
        if payment.unapplied_amount > 0:
            repository.upsert_ledger_entry(
                LedgerEntry(
                    id=f"led_supplier_advance_{saved.id}",
                    entry_type="supplier_advance",
                    source_type="supplier_payment",
                    source_id=saved.id,
                    amount=payment.unapplied_amount,
                    debit_account="Supplier Advance",
                    credit_account="Bank",
                )
            )
        return {
            "status": saved.status,
            "supplier_payment_id": saved.id,
            "supplier_payment": {**saved.model_dump(mode="json"), "supplier_payment_id": saved.id},
            "matched_purchase_invoice_id": invoice.id,
            "allocated_amount": allocation.amount,
            "unapplied_amount": saved.unapplied_amount,
            "allocations": [allocation.model_dump(mode="json")],
        }

    if len(exact_matches) > 1:
        candidates = exact_matches
    else:
        candidates = candidate_invoices

    payment = SupplierPayment(
        id=f"sup_pay_{uuid4().hex[:12]}",
        client_id=client_id,
        supplier_id=supplier_id,
        amount=amount,
        date=_parse_date(receipt.get("paid_on") or receipt.get("date")),
        mode=receipt.get("mode"),
        reference=receipt.get("reference"),
        status="needs_review",
        provider=receipt.get("provider"),
        external_event_id=external_event_id,
        source_event_type=receipt.get("source_event_type"),
        signature_verification_status=signature_status or "not_applicable_local_receipt",
    )
    repository.upsert_supplier_payment(payment)
    approvals.create_approval_request(
        client_id=client_id,
        action_type="review_supplier_payment_reconciliation",
        proposed_action="Review supplier payment reconciliation candidates",
        data={"supplier_payment_id": payment.id, "candidate_purchase_invoice_ids": [invoice.id for invoice in candidates]},
        reason="Supplier payment could not be deterministically matched to one invoice.",
        source="supplier_payment_reconciliation",
        confidence=0.55,
        dedupe_key=f"supplier_payment_review:{payment.reference or payment.id}",
    )
    return {
        "status": "needs_review",
        "supplier_payment_id": payment.id,
        "supplier_payment": {**payment.model_dump(mode="json"), "supplier_payment_id": payment.id},
        "candidate_purchase_invoice_ids": [invoice.id for invoice in candidates],
    }
