"""Local bank statement reconciliation contract."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Payment, PurchaseInvoice, RiskLevel, Supplier
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_BANK_RECONCILIATION_LIMITATION = (
    "Local bank-statement reconciliation only; no live bank feed, account aggregator, or banking API was called."
)


def _entry_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        return date.fromisoformat(value.strip())
    return None


def _normalized_entry(raw: dict[str, Any]) -> dict[str, Any]:
    direction = str(raw.get("direction") or "").strip().lower()
    if direction not in {"credit", "debit"}:
        raise ValueError("bank statement entry direction must be credit or debit")
    return {
        "entry_id": str(raw.get("entry_id") or raw.get("id") or f"bank_{uuid4().hex[:12]}"),
        "posted_on": _entry_date(raw.get("posted_on") or raw.get("date")),
        "direction": direction,
        "amount": round(float(raw.get("amount", 0)), 2),
        "reference": str(raw.get("reference") or "").strip(),
        "narration": str(raw.get("narration") or "").strip(),
    }


def _payment_match_row(entry: dict[str, Any], payment: Payment, code: str) -> dict[str, Any]:
    return {
        "bank_entry_id": entry["entry_id"],
        "direction": entry["direction"],
        "amount": entry["amount"],
        "matched_record_type": "payment",
        "matched_record_id": payment.id,
        "code": code,
    }


def _purchase_match_row(entry: dict[str, Any], invoice: PurchaseInvoice, code: str) -> dict[str, Any]:
    return {
        "bank_entry_id": entry["entry_id"],
        "direction": entry["direction"],
        "amount": entry["amount"],
        "matched_record_type": "purchase_invoice",
        "matched_record_id": invoice.id,
        "code": code,
    }


def _review_row(
    entry: dict[str, Any],
    *,
    candidate_record_type: str | None,
    candidate_record_ids: list[str],
    code: str,
) -> dict[str, Any]:
    return {
        "bank_entry_id": entry["entry_id"],
        "direction": entry["direction"],
        "amount": entry["amount"],
        "candidate_record_type": candidate_record_type,
        "candidate_record_ids": candidate_record_ids,
        "code": code,
    }


def _match_credit(entry: dict[str, Any], payments: list[Payment]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if entry["reference"]:
        reference_matches = [
            payment
            for payment in payments
            if payment.reference and payment.reference.strip().lower() == entry["reference"].lower()
        ]
        if len(reference_matches) == 1:
            return _payment_match_row(entry, reference_matches[0], "reference_match"), None
        if len(reference_matches) > 1:
            return None, _review_row(
                entry,
                candidate_record_type="payment",
                candidate_record_ids=[payment.id for payment in reference_matches],
                code="ambiguous_reference_match",
            )

    amount_matches = [
        payment
        for payment in payments
        if round(float(payment.amount), 2) == entry["amount"]
    ]
    if len(amount_matches) == 1:
        return _payment_match_row(entry, amount_matches[0], "amount_match"), None
    if len(amount_matches) > 1:
        return None, _review_row(
            entry,
            candidate_record_type="payment",
            candidate_record_ids=[payment.id for payment in amount_matches],
            code="ambiguous_amount_match",
        )
    return None, _review_row(entry, candidate_record_type=None, candidate_record_ids=[], code="unmatched_bank_entry")


def _payable_amount(invoice: PurchaseInvoice) -> float:
    return round(float(invoice.taxable_value) + float(invoice.tax_amount), 2)


def _supplier_name_lookup(suppliers: list[Supplier]) -> dict[str, str]:
    return {supplier.id: supplier.name for supplier in suppliers}


def _match_debit(
    entry: dict[str, Any],
    purchase_invoices: list[PurchaseInvoice],
    suppliers: dict[str, str],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    narration = entry["narration"].lower()
    amount_matches = [
        invoice
        for invoice in purchase_invoices
        if _payable_amount(invoice) == entry["amount"] and invoice.status.strip().lower() != "paid"
    ]
    narration_matches = [
        invoice
        for invoice in amount_matches
        if invoice.invoice_number.lower() in narration
        or (invoice.supplier_id and suppliers.get(invoice.supplier_id, "").lower() in narration)
    ]
    if len(narration_matches) == 1:
        return _purchase_match_row(entry, narration_matches[0], "supplier_amount_narration_match"), None
    if len(narration_matches) > 1:
        return None, _review_row(
            entry,
            candidate_record_type="purchase_invoice",
            candidate_record_ids=[invoice.id for invoice in narration_matches],
            code="ambiguous_supplier_narration_match",
        )
    if len(amount_matches) == 1:
        return _purchase_match_row(entry, amount_matches[0], "supplier_amount_match"), None
    if len(amount_matches) > 1:
        return None, _review_row(
            entry,
            candidate_record_type="purchase_invoice",
            candidate_record_ids=[invoice.id for invoice in amount_matches],
            code="ambiguous_amount_match",
        )
    return None, _review_row(entry, candidate_record_type=None, candidate_record_ids=[], code="unmatched_bank_entry")


def reconcile_bank_statement(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    statement_entries: list[dict[str, Any]],
    requested_by: str,
) -> dict[str, Any]:
    """Reconcile structured bank statement rows against local payment and payable records."""
    entries = [_normalized_entry(entry) for entry in statement_entries]
    payments = repository.get_payments()
    purchase_invoices = repository.get_purchase_invoices()
    suppliers = _supplier_name_lookup(repository.get_suppliers())
    matched_entries: list[dict[str, Any]] = []
    review_entries: list[dict[str, Any]] = []

    for entry in entries:
        if entry["direction"] == "credit":
            matched, review = _match_credit(entry, payments)
        else:
            matched, review = _match_debit(entry, purchase_invoices, suppliers)
        if matched is not None:
            matched_entries.append(matched)
        if review is not None:
            review_entries.append(review)

    summary = {
        "entries": len(entries),
        "credit_total": round(sum(entry["amount"] for entry in entries if entry["direction"] == "credit"), 2),
        "debit_total": round(sum(entry["amount"] for entry in entries if entry["direction"] == "debit"), 2),
        "matched_customer_receipts": sum(1 for entry in matched_entries if entry["matched_record_type"] == "payment"),
        "matched_supplier_payments": sum(1 for entry in matched_entries if entry["matched_record_type"] == "purchase_invoice"),
        "ambiguous_entries": sum(1 for entry in review_entries if entry["code"].startswith("ambiguous")),
        "unmatched_entries": sum(1 for entry in review_entries if entry["code"] == "unmatched_bank_entry"),
    }
    audit = {
        "requested_by": requested_by,
        "external_bank_feed_called": False,
        "account_aggregator_called": False,
        "ledger_posting_performed": False,
        "limitation": LOCAL_BANK_RECONCILIATION_LIMITATION,
    }
    result = {
        "mode": "local_contract_mock",
        "status": "needs_review" if review_entries else "matched",
        "summary": summary,
        "matched_entries": matched_entries,
        "review_entries": review_entries,
        "audit": audit,
    }
    if review_entries:
        batch_id = f"bank_reco_{uuid4().hex[:12]}"
        approval = approvals.create_approval_request(
            client_id=client_id,
            action_type="review_bank_statement_reconciliation",
            proposed_action="Review local bank statement reconciliation exceptions",
            data={
                "batch_id": batch_id,
                "summary": summary,
                "matched_entries": matched_entries,
                "review_entries": review_entries,
                "mode": "local_contract_mock",
            },
            reason="Bank statement exceptions can affect ledger and cash position; owner/accountant review is required first.",
            source="bank_reconciliation",
            confidence=0.7,
            risk_level=RiskLevel.high,
            dedupe_key=f"bank_reconciliation:{client_id}:{batch_id}",
        )
        result["batch_id"] = batch_id
        result["approval_id"] = approval.id
    return result
