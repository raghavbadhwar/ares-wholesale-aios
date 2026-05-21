"""Local TDS/TCS computation review."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, PurchaseInvoice, RiskLevel, Supplier
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_TDS_TCS_LIMITATION = (
    "Local TDS/TCS computation review only; no income-tax portal, challan payment, TRACES, or statutory filing integration was called."
)
TCS_SECTION = "206C(1H)"
TCS_THRESHOLD = 5_000_000.0
TCS_RATE_PERCENT = 0.1
EXCLUDED_INVOICE_STATUSES = {"cancelled", "void"}


def _period_bounds(period: str) -> tuple[date, date]:
    year_raw, month_raw = period.split("-", 1)
    year = int(year_raw)
    month = int(month_raw)
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _customer_lookup(repository: BusinessRepository) -> dict[str, Customer]:
    return {customer.id: customer for customer in repository.get_customers()}


def _supplier_lookup(repository: BusinessRepository) -> dict[str, Supplier]:
    return {supplier.id: supplier for supplier in repository.get_suppliers()}


def _invoice_taxable_value(invoice: Any) -> float:
    return round(float(invoice.taxable_value if invoice.taxable_value is not None else invoice.amount), 2)


def _build_tcs_rows(
    *,
    repository: BusinessRepository,
    period_start: date,
    period_end: date,
    fiscal_year_start: date,
) -> list[dict[str, Any]]:
    customers = _customer_lookup(repository)
    by_customer: dict[str, dict[str, float]] = {}
    for invoice in repository.get_invoices():
        if not invoice.customer_id or invoice.date is None or invoice.date < fiscal_year_start or invoice.date > period_end:
            continue
        if invoice.status.strip().lower() in EXCLUDED_INVOICE_STATUSES:
            continue
        bucket = by_customer.setdefault(invoice.customer_id, {"fy": 0.0, "prior": 0.0, "current": 0.0})
        amount = _invoice_taxable_value(invoice)
        bucket["fy"] = round(bucket["fy"] + amount, 2)
        if invoice.date < period_start:
            bucket["prior"] = round(bucket["prior"] + amount, 2)
        elif period_start <= invoice.date <= period_end:
            bucket["current"] = round(bucket["current"] + amount, 2)

    rows: list[dict[str, Any]] = []
    for customer_id, bucket in by_customer.items():
        fy_above_threshold = max(bucket["fy"] - TCS_THRESHOLD, 0.0)
        prior_above_threshold = max(bucket["prior"] - TCS_THRESHOLD, 0.0)
        taxable_for_tcs = round(max(fy_above_threshold - prior_above_threshold, 0.0), 2)
        if taxable_for_tcs <= 0 or bucket["current"] <= 0:
            continue
        taxable_for_tcs = min(taxable_for_tcs, bucket["current"])
        customer = customers.get(customer_id)
        rows.append(
            {
                "customer_id": customer_id,
                "customer_name": customer.name if customer else None,
                "section": TCS_SECTION,
                "current_period_taxable_sales": round(bucket["current"], 2),
                "fy_taxable_sales": round(bucket["fy"], 2),
                "threshold": TCS_THRESHOLD,
                "taxable_for_tcs": round(taxable_for_tcs, 2),
                "rate_percent": TCS_RATE_PERCENT,
                "tcs_amount": round(taxable_for_tcs * (TCS_RATE_PERCENT / 100), 2),
            }
        )
    return rows


def _tds_base(invoice: PurchaseInvoice) -> float:
    if invoice.tds_base_amount is not None:
        return round(float(invoice.tds_base_amount), 2)
    return round(float(invoice.taxable_value), 2)


def _build_tds_rows(
    *,
    repository: BusinessRepository,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    suppliers = _supplier_lookup(repository)
    rows: list[dict[str, Any]] = []
    for invoice in repository.get_purchase_invoices():
        if invoice.date is None or invoice.date < period_start or invoice.date > period_end:
            continue
        if invoice.status.strip().lower() in EXCLUDED_INVOICE_STATUSES:
            continue
        if not invoice.tds_section or invoice.tds_rate_percent is None:
            continue
        base_amount = _tds_base(invoice)
        supplier = suppliers.get(invoice.supplier_id or "")
        rows.append(
            {
                "purchase_invoice_id": invoice.id,
                "supplier_id": invoice.supplier_id,
                "supplier_name": supplier.name if supplier else None,
                "section": invoice.tds_section,
                "tds_base_amount": base_amount,
                "rate_percent": float(invoice.tds_rate_percent),
                "tds_amount": round(base_amount * (float(invoice.tds_rate_percent) / 100), 2),
            }
        )
    return rows


def prepare_tds_tcs_computation(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    period: str,
    fiscal_year_start: date,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare local TDS/TCS rows for accountant review."""
    period_start, period_end = _period_bounds(period)
    tcs_rows = _build_tcs_rows(
        repository=repository,
        period_start=period_start,
        period_end=period_end,
        fiscal_year_start=fiscal_year_start,
    )
    tds_rows = _build_tds_rows(repository=repository, period_start=period_start, period_end=period_end)
    tcs_amount = round(sum(float(row["tcs_amount"]) for row in tcs_rows), 2)
    tds_amount = round(sum(float(row["tds_amount"]) for row in tds_rows), 2)
    summary = {
        "tcs_customers": len(tcs_rows),
        "tcs_amount": tcs_amount,
        "tds_payables": len(tds_rows),
        "tds_amount": tds_amount,
        "total_withholding_review": round(tcs_amount + tds_amount, 2),
        "validation_errors": 0,
    }
    audit = {
        "requested_by": requested_by,
        "external_income_tax_portal_called": False,
        "challan_payment_performed": False,
        "statutory_filing_performed": False,
        "limitation": LOCAL_TDS_TCS_LIMITATION,
    }
    if not tcs_rows and not tds_rows:
        return {
            "mode": "local_contract_mock",
            "status": "no_withholding_review_needed",
            "period": period,
            "summary": summary,
            "tcs_rows": [],
            "tds_rows": [],
            "validation_errors": [],
            "audit": audit,
        }

    batch_id = f"tds_tcs_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_tds_tcs_computation",
        proposed_action=f"Review local TDS/TCS computation for {period}",
        data={
            "batch_id": batch_id,
            "period": period,
            "fiscal_year_start": fiscal_year_start.isoformat(),
            "summary": summary,
            "tcs_rows": tcs_rows,
            "tds_rows": tds_rows,
            "mode": "local_contract_mock",
        },
        reason="TDS/TCS computation affects statutory withholding and must be reviewed before filing or payment.",
        source="tds_tcs",
        confidence=0.85,
        risk_level=RiskLevel.high,
        dedupe_key=f"tds_tcs:{client_id}:{period}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "period": period,
        "summary": summary,
        "tcs_rows": tcs_rows,
        "tds_rows": tds_rows,
        "validation_errors": [],
        "audit": audit,
    }
