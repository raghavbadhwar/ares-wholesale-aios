"""Local supplier payment scheduling contract."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import PurchaseInvoice, RiskLevel, Supplier
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_SUPPLIER_PAYMENT_LIMITATION = "Local supplier payment schedule only; no banking or UPI payment was executed."
OPEN_PAYABLE_STATUSES = {"booked", "open", "unpaid", "due", "overdue"}


def _supplier_by_id(repository: BusinessRepository) -> dict[str, Supplier]:
    return {supplier.id: supplier for supplier in repository.get_suppliers()}


def _payable_amount(invoice: PurchaseInvoice) -> float:
    return round(float(invoice.taxable_value) + float(invoice.tax_amount), 2)


def _priority(invoice: PurchaseInvoice, as_of: date) -> str:
    if invoice.due_date and invoice.due_date < as_of:
        return "overdue"
    if invoice.early_payment_discount_amount > 0 and invoice.early_payment_discount_deadline:
        if as_of <= invoice.early_payment_discount_deadline <= as_of + timedelta(days=7):
            return "early_payment_discount"
    if invoice.due_date and as_of <= invoice.due_date <= as_of + timedelta(days=7):
        return "due_soon"
    return "scheduled"


def _sort_key(invoice: PurchaseInvoice, as_of: date) -> tuple[int, date, str]:
    priority_rank = {"overdue": 0, "early_payment_discount": 1, "due_soon": 2, "scheduled": 3}
    fallback_date = date.max
    return (priority_rank[_priority(invoice, as_of)], invoice.due_date or fallback_date, invoice.invoice_number)


def _payment_row(
    *,
    invoice: PurchaseInvoice,
    supplier: Supplier | None,
    as_of: date,
    recommended_amount: float,
) -> dict[str, Any]:
    return {
        "purchase_invoice_id": invoice.id,
        "supplier_id": invoice.supplier_id,
        "supplier_name": supplier.name if supplier else None,
        "supplier_gstin": invoice.supplier_gstin,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.date.isoformat() if invoice.date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "priority": _priority(invoice, as_of),
        "payable_amount": _payable_amount(invoice),
        "recommended_amount": recommended_amount,
        "discount_amount": float(invoice.early_payment_discount_amount),
        "discount_deadline": invoice.early_payment_discount_deadline.isoformat() if invoice.early_payment_discount_deadline else None,
    }


def prepare_supplier_payment_schedule(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    as_of: date,
    cash_available: float,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare an approval-gated local supplier payment plan."""
    suppliers = _supplier_by_id(repository)
    payables = [
        invoice
        for invoice in repository.get_purchase_invoices()
        if invoice.status.strip().lower() in OPEN_PAYABLE_STATUSES
    ]
    payables.sort(key=lambda invoice: _sort_key(invoice, as_of))
    total_payable = round(sum(_payable_amount(invoice) for invoice in payables), 2)
    overdue_count = sum(1 for invoice in payables if invoice.due_date and invoice.due_date < as_of)
    due_next_7_days = sum(1 for invoice in payables if invoice.due_date and as_of <= invoice.due_date <= as_of + timedelta(days=7))
    discount_count = sum(
        1
        for invoice in payables
        if invoice.early_payment_discount_amount > 0
        and invoice.early_payment_discount_deadline
        and as_of <= invoice.early_payment_discount_deadline <= as_of + timedelta(days=7)
    )
    recommended_total = min(round(float(cash_available), 2), total_payable)
    remaining_cash = recommended_total
    recommended_payments: list[dict[str, Any]] = []
    for invoice in payables:
        if remaining_cash <= 0:
            recommended_amount = 0.0
        else:
            recommended_amount = min(_payable_amount(invoice), remaining_cash)
            remaining_cash = round(remaining_cash - recommended_amount, 2)
        recommended_payments.append(
            _payment_row(
                invoice=invoice,
                supplier=suppliers.get(invoice.supplier_id or ""),
                as_of=as_of,
                recommended_amount=round(recommended_amount, 2),
            )
        )

    summary = {
        "payable_count": len(payables),
        "overdue_count": overdue_count,
        "due_next_7_days": due_next_7_days,
        "early_payment_discount_opportunities": discount_count,
        "total_payable": total_payable,
        "recommended_payment_amount": recommended_total,
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": bool(payables),
        "external_payment_performed": False,
        "limitation": LOCAL_SUPPLIER_PAYMENT_LIMITATION,
    }
    if not payables:
        return {
            "mode": "local_contract_mock",
            "status": "no_open_payables",
            "summary": summary,
            "recommended_payments": [],
            "audit": audit,
        }

    batch_id = f"supplier_pay_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="schedule_supplier_payments",
        proposed_action=f"Review supplier payment schedule for {as_of.isoformat()}",
        data={
            "batch_id": batch_id,
            "as_of": as_of.isoformat(),
            "cash_available": round(float(cash_available), 2),
            "summary": summary,
            "recommended_payments": recommended_payments,
            "mode": "local_contract_mock",
        },
        reason="Supplier payment plans affect cash flow and bank execution; owner approval is required first.",
        source="supplier_payments",
        confidence=0.9,
        risk_level=RiskLevel.high,
        dedupe_key=f"supplier_payments:{client_id}:{as_of.isoformat()}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "summary": summary,
        "recommended_payments": recommended_payments,
        "audit": audit,
    }
