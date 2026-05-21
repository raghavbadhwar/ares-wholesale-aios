"""Local daily cash-flow statement."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.ares.ares.data.models import Invoice, Payment, PostDatedCheque, PurchaseInvoice
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_CASH_FLOW_LIMITATION = (
    "Local daily cash-flow statement only; no bank, payment gateway, or accounting close integration was called."
)
OPEN_RECEIVABLE_STATUSES = {"open", "overdue", "due", "unpaid"}
OPEN_PAYABLE_STATUSES = {"booked", "open", "unpaid", "due", "overdue"}


def _payment_row(payment: Payment) -> dict[str, Any]:
    return {
        "payment_id": payment.id,
        "customer_id": payment.customer_id,
        "amount": float(payment.amount),
        "mode": payment.mode,
        "reference": payment.reference,
        "status": payment.status,
    }


def _invoice_row(invoice: Invoice) -> dict[str, Any]:
    return {
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "customer_id": invoice.customer_id,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "amount": float(invoice.amount),
        "status": invoice.status,
    }


def _pdc_row(cheque: PostDatedCheque) -> dict[str, Any]:
    return {
        "pdc_id": cheque.id,
        "party_id": cheque.party_id,
        "amount": float(cheque.amount),
        "cheque_date": cheque.cheque_date.isoformat(),
        "bank_name": cheque.bank_name,
        "status": cheque.status,
    }


def _payable_amount(invoice: PurchaseInvoice) -> float:
    return round(float(invoice.taxable_value) + float(invoice.tax_amount), 2)


def _purchase_invoice_row(invoice: PurchaseInvoice) -> dict[str, Any]:
    return {
        "purchase_invoice_id": invoice.id,
        "supplier_id": invoice.supplier_id,
        "invoice_number": invoice.invoice_number,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "amount": _payable_amount(invoice),
        "status": invoice.status,
    }


def _is_due_on_or_before(value: date | None, as_of: date) -> bool:
    return value is not None and value <= as_of


def build_daily_cash_flow_statement(
    *,
    repository: BusinessRepository,
    as_of: date,
    opening_cash: float,
) -> dict[str, Any]:
    """Build a local daily cash-flow statement from receipts, receivables, PDCs, and payables."""
    payments = [
        payment
        for payment in repository.get_payments()
        if payment.date == as_of
    ]
    expected_collection_invoices = [
        invoice
        for invoice in repository.get_invoices()
        if invoice.status.strip().lower() in OPEN_RECEIVABLE_STATUSES
        and _is_due_on_or_before(invoice.due_date, as_of)
    ]
    expected_collection_invoices.sort(key=lambda invoice: (invoice.due_date or date.max, invoice.invoice_number))

    pdc_inflows = [
        cheque
        for cheque in repository.get_post_dated_cheques()
        if cheque.cheque_date == as_of and cheque.status.strip().lower() in {"scheduled", "deposited"}
    ]
    supplier_outflow_invoices = [
        invoice
        for invoice in repository.get_purchase_invoices()
        if invoice.status.strip().lower() in OPEN_PAYABLE_STATUSES
        and _is_due_on_or_before(invoice.due_date, as_of)
    ]
    supplier_outflow_invoices.sort(key=lambda invoice: (invoice.due_date or date.max, invoice.invoice_number))

    actual_inflows = [_payment_row(payment) for payment in payments]
    expected_collections = [_invoice_row(invoice) for invoice in expected_collection_invoices]
    scheduled_pdc_inflows = [_pdc_row(cheque) for cheque in pdc_inflows]
    supplier_outflows = [_purchase_invoice_row(invoice) for invoice in supplier_outflow_invoices]

    actual_inflow_amount = round(sum(row["amount"] for row in actual_inflows), 2)
    expected_collection_amount = round(sum(row["amount"] for row in expected_collections), 2)
    pdc_amount = round(sum(row["amount"] for row in scheduled_pdc_inflows), 2)
    supplier_outflow_amount = round(sum(row["amount"] for row in supplier_outflows), 2)
    net_cash_movement = round(actual_inflow_amount + expected_collection_amount + pdc_amount - supplier_outflow_amount, 2)
    projected_closing_cash = round(float(opening_cash) + net_cash_movement, 2)

    return {
        "mode": "local_contract_mock",
        "as_of": as_of.isoformat(),
        "summary": {
            "opening_cash": round(float(opening_cash), 2),
            "actual_inflows": actual_inflow_amount,
            "expected_collections_due": expected_collection_amount,
            "scheduled_pdc_inflows": pdc_amount,
            "supplier_outflows_due": supplier_outflow_amount,
            "net_cash_movement": net_cash_movement,
            "projected_closing_cash": projected_closing_cash,
        },
        "actual_inflows": actual_inflows,
        "expected_collections": expected_collections,
        "scheduled_pdc_inflows": scheduled_pdc_inflows,
        "supplier_outflows": supplier_outflows,
        "risks": {
            "overdue_receivables": sum(1 for invoice in expected_collection_invoices if invoice.due_date and invoice.due_date < as_of),
            "overdue_payables": sum(1 for invoice in supplier_outflow_invoices if invoice.due_date and invoice.due_date < as_of),
            "unreconciled_inflows": sum(1 for payment in payments if payment.status.strip().lower() in {"unreconciled", "needs_review"}),
        },
        "audit": {
            "external_bank_balance_called": False,
            "external_payment_gateway_called": False,
            "external_accounting_close_performed": False,
            "limitation": LOCAL_CASH_FLOW_LIMITATION,
        },
    }
