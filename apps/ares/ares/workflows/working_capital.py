"""Local working-capital intelligence."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.ares.ares.data.models import Invoice, ProductSKU, PurchaseInvoice
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_WORKING_CAPITAL_LIMITATION = (
    "Local working-capital intelligence only; no bank, account-aggregator, or financing integration was called."
)
OPEN_RECEIVABLE_STATUSES = {"open", "overdue", "due", "unpaid"}
OPEN_PAYABLE_STATUSES = {"booked", "open", "overdue", "due", "unpaid"}


def _invoice_amounts(invoices: list[Invoice], as_of: date) -> tuple[float, float]:
    receivables = 0.0
    overdue = 0.0
    for invoice in invoices:
        status = invoice.status.strip().lower()
        if status not in OPEN_RECEIVABLE_STATUSES:
            continue
        amount = float(invoice.amount)
        receivables += amount
        if status == "overdue" or (invoice.due_date is not None and invoice.due_date < as_of):
            overdue += amount
    return round(receivables, 2), round(overdue, 2)


def _payable_amount(invoice: PurchaseInvoice) -> float:
    return round(float(invoice.taxable_value) + float(invoice.tax_amount), 2)


def _payables(invoices: list[PurchaseInvoice]) -> float:
    return round(
        sum(_payable_amount(invoice) for invoice in invoices if invoice.status.strip().lower() in OPEN_PAYABLE_STATUSES),
        2,
    )


def _inventory_value(products: list[ProductSKU]) -> float:
    return round(sum(float(product.current_stock) * float(product.buying_price or 0) for product in products), 2)


def _low_stock_count(products: list[ProductSKU]) -> int:
    return sum(1 for product in products if product.current_stock < product.reorder_level)


def _scheduled_pdc_inflows(repository: BusinessRepository, as_of: date) -> float:
    return round(
        sum(
            float(cheque.amount)
            for cheque in repository.get_post_dated_cheques()
            if cheque.status.strip().lower() in {"scheduled", "deposited"} and cheque.cheque_date >= as_of
        ),
        2,
    )


def build_working_capital_intelligence(
    *,
    repository: BusinessRepository,
    as_of: date,
    opening_cash: float,
) -> dict[str, Any]:
    """Build a local working-capital snapshot from operating records."""
    products = repository.get_products()
    receivables, overdue_receivables = _invoice_amounts(repository.get_invoices(), as_of)
    payables = _payables(repository.get_purchase_invoices())
    inventory_value = _inventory_value(products)
    pdc_inflows = _scheduled_pdc_inflows(repository, as_of)
    cash_on_hand = round(float(opening_cash), 2)
    net_working_capital = round(cash_on_hand + receivables + inventory_value + pdc_inflows - payables, 2)

    low_stock_count = _low_stock_count(products)
    risk_flags: list[dict[str, Any]] = []
    if overdue_receivables > 0:
        risk_flags.append({"code": "overdue_receivable_pressure", "amount": overdue_receivables})
    if payables > cash_on_hand:
        risk_flags.append({"code": "payable_pressure", "amount": round(payables - cash_on_hand, 2)})
    if low_stock_count:
        risk_flags.append({"code": "low_stock_replenishment_needed", "sku_count": low_stock_count})

    return {
        "mode": "local_contract_mock",
        "as_of": as_of.isoformat(),
        "summary": {
            "cash_on_hand": cash_on_hand,
            "receivables": receivables,
            "overdue_receivables": overdue_receivables,
            "payables": payables,
            "inventory_value": inventory_value,
            "scheduled_pdc_inflows": pdc_inflows,
            "net_working_capital": net_working_capital,
        },
        "risk_flags": risk_flags,
        "audit": {
            "external_bank_balance_called": False,
            "account_aggregator_called": False,
            "financing_offer_generated": False,
            "limitation": LOCAL_WORKING_CAPITAL_LIMITATION,
        },
    }
