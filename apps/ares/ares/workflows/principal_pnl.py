"""Local principal-wise P&L analytics."""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from typing import Any

from apps.ares.ares.data.models import Invoice, Principal, ProductSKU
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_PRINCIPAL_PNL_LIMITATION = "Local principal-wise P&L analytics only; no ERP close, bank, or accounting integration was called."


def _period_bounds(period: str) -> tuple[date, date]:
    year_raw, month_raw = period.split("-", 1)
    year = int(year_raw)
    month = int(month_raw)
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _invoice_in_period(invoice: Invoice, start: date, end: date) -> bool:
    return invoice.date is not None and start <= invoice.date <= end


def _empty_principal_row(principal: Principal) -> dict[str, Any]:
    return {
        "principal_id": principal.id,
        "principal_name": principal.name,
        "revenue": 0.0,
        "estimated_cogs": 0.0,
        "gross_margin": 0.0,
        "gross_margin_percent": 0.0,
        "scheme_claims": 0.0,
        "net_margin_after_claims": 0.0,
        "low_stock_skus": [],
    }


def build_principal_pnl(*, repository: BusinessRepository, period: str) -> dict[str, Any]:
    """Build a local principal-wise P&L view from sales, product cost, and claim data."""
    period_start, period_end = _period_bounds(period)
    principals = {principal.id: principal for principal in repository.get_principals()}
    products = {product.id: product for product in repository.get_products()}
    rows = {principal.id: _empty_principal_row(principal) for principal in principals.values()}
    unattributed_lines: list[dict[str, Any]] = []

    for invoice in repository.get_invoices():
        if not _invoice_in_period(invoice, period_start, period_end):
            continue
        for line in invoice.line_items:
            product = products.get(line.sku_id or "")
            taxable_value = round(float(line.taxable_value), 2)
            if product is None or not product.principal_id or product.principal_id not in rows:
                unattributed_lines.append(
                    {
                        "invoice_id": invoice.id,
                        "sku_id": line.sku_id,
                        "taxable_value": taxable_value,
                        "code": "principal_missing",
                    }
                )
                continue
            row = rows[product.principal_id]
            quantity = float(line.quantity or 0)
            estimated_cogs = round(quantity * float(product.buying_price or 0), 2)
            row["revenue"] = round(row["revenue"] + taxable_value, 2)
            row["estimated_cogs"] = round(row["estimated_cogs"] + estimated_cogs, 2)

    for claim in repository.get_scheme_claims():
        if claim.principal_id in rows and claim.status in {"approved", "submitted", "settled", "draft"}:
            rows[claim.principal_id]["scheme_claims"] = round(
                rows[claim.principal_id]["scheme_claims"] + float(claim.claim_amount),
                2,
            )

    for product in products.values():
        if product.principal_id in rows and product.current_stock < product.reorder_level:
            rows[product.principal_id]["low_stock_skus"].append(product.id)

    principal_rows = []
    for row in rows.values():
        row["gross_margin"] = round(float(row["revenue"]) - float(row["estimated_cogs"]), 2)
        row["gross_margin_percent"] = round((float(row["gross_margin"]) / float(row["revenue"])) * 100, 2) if row["revenue"] else 0.0
        row["net_margin_after_claims"] = round(float(row["gross_margin"]) + float(row["scheme_claims"]), 2)
        principal_rows.append(row)
    principal_rows.sort(key=lambda item: item["principal_name"])

    summary = {
        "principals": len([row for row in principal_rows if row["revenue"] or row["scheme_claims"] or row["low_stock_skus"]]),
        "revenue": round(sum(float(row["revenue"]) for row in principal_rows), 2),
        "gross_margin": round(sum(float(row["gross_margin"]) for row in principal_rows), 2),
        "scheme_claims": round(sum(float(row["scheme_claims"]) for row in principal_rows), 2),
        "low_stock_principals": sum(1 for row in principal_rows if row["low_stock_skus"]),
    }
    return {
        "mode": "local_contract_mock",
        "period": period,
        "summary": summary,
        "principals": principal_rows,
        "unattributed_lines": unattributed_lines,
        "audit": {
            "external_accounting_close_performed": False,
            "limitation": LOCAL_PRINCIPAL_PNL_LIMITATION,
        },
    }
