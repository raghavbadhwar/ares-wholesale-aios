"""Local retailer segmentation analytics."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from apps.ares.ares.data.models import Customer, Invoice, Payment
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_RETAILER_SEGMENTATION_LIMITATION = (
    "Local retailer segmentation only; no predictive ML model or CRM enrichment integration was called."
)
OPEN_INVOICE_STATUSES = {"open", "overdue", "due", "unpaid"}
OVERDUE_STATUSES = {"overdue"}
PRIORITY_REVENUE_THRESHOLD = 50000.0


def _in_lookback(value: date | None, start: date, end: date) -> bool:
    return value is not None and start <= value <= end


def _customer_invoices(invoices: list[Invoice], customer: Customer) -> list[Invoice]:
    return [invoice for invoice in invoices if invoice.customer_id == customer.id]


def _customer_payments(payments: list[Payment], customer: Customer) -> list[Payment]:
    return [payment for payment in payments if payment.customer_id == customer.id]


def _days_since_last_invoice(invoices: list[Invoice], as_of: date) -> int | None:
    invoice_dates = [invoice.date for invoice in invoices if invoice.date is not None and invoice.date <= as_of]
    if not invoice_dates:
        return None
    return (as_of - max(invoice_dates)).days


def _credit_utilization(customer: Customer, outstanding_amount: float) -> float:
    if not customer.credit_limit:
        return 0.0
    return round((outstanding_amount / float(customer.credit_limit)) * 100, 2)


def _segment_for(
    *,
    revenue: float,
    overdue_amount: float,
    credit_utilization_percent: float,
    days_since_last_invoice: int | None,
    lookback_days: int,
) -> str:
    if overdue_amount > 0 or credit_utilization_percent > 100:
        return "credit_risk"
    if revenue >= PRIORITY_REVENUE_THRESHOLD:
        return "priority_retailer"
    if days_since_last_invoice is None or days_since_last_invoice > lookback_days:
        return "dormant_or_untraded"
    return "regular_retailer"


def _recommended_action(segment: str) -> str:
    return {
        "credit_risk": "Owner review before fresh dispatch; recover overdue or approve credit exception.",
        "priority_retailer": "Protect service level and check next reorder opportunity.",
        "dormant_or_untraded": "Ask salesman to verify relationship status before planning offers.",
        "regular_retailer": "Continue normal beat coverage and monitor reorder cadence.",
    }[segment]


def build_retailer_segmentation(
    *,
    repository: BusinessRepository,
    as_of: date,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Build local retailer segments from customer, invoice, payment, and credit signals."""
    lookback_start = as_of - timedelta(days=lookback_days)
    invoices = repository.get_invoices()
    payments = repository.get_payments()
    segments: list[dict[str, Any]] = []

    for customer in repository.get_customers():
        customer_invoices = _customer_invoices(invoices, customer)
        customer_payments = _customer_payments(payments, customer)
        lookback_invoices = [invoice for invoice in customer_invoices if _in_lookback(invoice.date, lookback_start, as_of)]
        lookback_payments = [payment for payment in customer_payments if _in_lookback(payment.date, lookback_start, as_of)]
        revenue = round(sum(float(invoice.amount) for invoice in lookback_invoices), 2)
        paid_amount = round(sum(float(payment.amount) for payment in lookback_payments if payment.status != "unreconciled"), 2)
        outstanding_amount = round(
            sum(float(invoice.amount) for invoice in customer_invoices if invoice.status.strip().lower() in OPEN_INVOICE_STATUSES),
            2,
        )
        overdue_amount = round(
            sum(float(invoice.amount) for invoice in customer_invoices if invoice.status.strip().lower() in OVERDUE_STATUSES),
            2,
        )
        days_since_last_invoice = _days_since_last_invoice(customer_invoices, as_of)
        credit_utilization_percent = _credit_utilization(customer, outstanding_amount)
        segment = _segment_for(
            revenue=revenue,
            overdue_amount=overdue_amount,
            credit_utilization_percent=credit_utilization_percent,
            days_since_last_invoice=days_since_last_invoice,
            lookback_days=lookback_days,
        )
        segments.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "segment": segment,
                "revenue_last_90_days": revenue,
                "paid_amount_last_90_days": paid_amount,
                "outstanding_amount": outstanding_amount,
                "overdue_amount": overdue_amount,
                "days_since_last_invoice": days_since_last_invoice,
                "credit_utilization_percent": credit_utilization_percent,
                "recommended_action": _recommended_action(segment),
            }
        )

    segment_rank = {"credit_risk": 0, "priority_retailer": 1, "dormant_or_untraded": 2, "regular_retailer": 3}
    segments.sort(key=lambda row: (segment_rank[row["segment"]], row["customer_name"]))
    return {
        "mode": "local_contract_mock",
        "as_of": as_of.isoformat(),
        "lookback_days": lookback_days,
        "summary": {
            "customers": len(segments),
            "priority_retailers": sum(1 for row in segments if row["segment"] == "priority_retailer"),
            "credit_risk_retailers": sum(1 for row in segments if row["segment"] == "credit_risk"),
            "dormant_retailers": sum(1 for row in segments if row["segment"] == "dormant_or_untraded"),
            "total_revenue": round(sum(float(row["revenue_last_90_days"]) for row in segments), 2),
            "total_overdue": round(sum(float(row["overdue_amount"]) for row in segments), 2),
        },
        "segments": segments,
        "audit": {
            "external_crm_enrichment_called": False,
            "predictive_ml_model_called": False,
            "limitation": LOCAL_RETAILER_SEGMENTATION_LIMITATION,
        },
    }
