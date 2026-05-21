"""Local SKU performance intelligence."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from apps.ares.ares.data.models import InventoryBatch, Invoice, ProductSKU
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_SKU_PERFORMANCE_LIMITATION = (
    "Local SKU performance intelligence only; no demand forecasting model or external market intelligence was called."
)


def _invoice_in_window(invoice: Invoice, start: date, end: date) -> bool:
    return invoice.date is not None and start <= invoice.date <= end


def _empty_sku_row(product: ProductSKU) -> dict[str, Any]:
    return {
        "sku_id": product.id,
        "sku_name": product.name,
        "units_sold": 0.0,
        "revenue": 0.0,
        "estimated_cogs": 0.0,
        "gross_margin": 0.0,
        "gross_margin_percent": 0.0,
        "current_stock": round(float(product.current_stock), 2),
        "reorder_level": round(float(product.reorder_level), 2),
        "stock_status": "reorder_now" if product.current_stock < product.reorder_level else "healthy",
        "expiring_batches": [],
        "recommended_action": "Maintain current stock cadence.",
    }


def _batch_row(batch: InventoryBatch) -> dict[str, Any]:
    return {
        "batch_id": batch.id,
        "batch_code": batch.batch_code,
        "expiry_date": batch.expiry_date.isoformat() if batch.expiry_date else None,
        "quantity": round(float(batch.quantity), 2),
    }


def _recommended_action(row: dict[str, Any]) -> str:
    if row["stock_status"] == "reorder_now":
        return "Reorder or prioritize replenishment before stockout."
    if row["expiring_batches"]:
        return "Prioritize selling expiring stock before fresh replenishment."
    if row["units_sold"] == 0:
        return "Review slow movement and avoid fresh purchase until demand is clear."
    return "Maintain current stock cadence."


def build_sku_performance_intelligence(
    *,
    repository: BusinessRepository,
    as_of: date,
    lookback_days: int = 90,
    expiry_window_days: int = 30,
) -> dict[str, Any]:
    """Build local SKU performance analytics from invoices, products, and batches."""
    window_start = as_of - timedelta(days=max(0, lookback_days))
    expiry_end = as_of + timedelta(days=max(0, expiry_window_days))
    products = {product.id: product for product in repository.get_products()}
    rows = {sku_id: _empty_sku_row(product) for sku_id, product in products.items()}
    unattributed_lines: list[dict[str, Any]] = []

    for invoice in repository.get_invoices():
        if not _invoice_in_window(invoice, window_start, as_of):
            continue
        for line in invoice.line_items:
            taxable_value = round(float(line.taxable_value), 2)
            product = products.get(line.sku_id or "")
            if product is None:
                unattributed_lines.append(
                    {
                        "invoice_id": invoice.id,
                        "sku_id": line.sku_id,
                        "taxable_value": taxable_value,
                        "code": "sku_missing",
                    }
                )
                continue
            row = rows[product.id]
            quantity = float(line.quantity or 0)
            estimated_cogs = round(quantity * float(product.buying_price or 0), 2)
            row["units_sold"] = round(float(row["units_sold"]) + quantity, 2)
            row["revenue"] = round(float(row["revenue"]) + taxable_value, 2)
            row["estimated_cogs"] = round(float(row["estimated_cogs"]) + estimated_cogs, 2)

    for batch in repository.get_inventory_batches():
        if batch.sku_id not in rows or batch.expiry_date is None:
            continue
        if as_of <= batch.expiry_date <= expiry_end and batch.quantity > 0:
            rows[batch.sku_id]["expiring_batches"].append(_batch_row(batch))

    sku_rows = []
    for row in rows.values():
        row["gross_margin"] = round(float(row["revenue"]) - float(row["estimated_cogs"]), 2)
        row["gross_margin_percent"] = (
            round((float(row["gross_margin"]) / float(row["revenue"])) * 100, 2) if row["revenue"] else 0.0
        )
        row["expiring_batches"].sort(key=lambda item: (item["expiry_date"] or "", item["batch_code"]))
        row["recommended_action"] = _recommended_action(row)
        sku_rows.append(row)

    sku_rows.sort(key=lambda item: (float(item["gross_margin"]), float(item["revenue"]), item["sku_name"]), reverse=True)
    summary = {
        "skus": len(sku_rows),
        "units_sold": round(sum(float(row["units_sold"]) for row in sku_rows), 2),
        "revenue": round(sum(float(row["revenue"]) for row in sku_rows), 2),
        "gross_margin": round(sum(float(row["gross_margin"]) for row in sku_rows), 2),
        "low_stock_skus": sum(1 for row in sku_rows if row["stock_status"] == "reorder_now"),
        "expiring_batches": sum(len(row["expiring_batches"]) for row in sku_rows),
        "unattributed_lines": len(unattributed_lines),
    }
    return {
        "mode": "local_contract_mock",
        "as_of": as_of.isoformat(),
        "lookback_days": lookback_days,
        "summary": summary,
        "sku_performance": sku_rows,
        "unattributed_lines": unattributed_lines,
        "audit": {
            "predictive_demand_model_called": False,
            "external_market_intelligence_called": False,
            "limitation": LOCAL_SKU_PERFORMANCE_LIMITATION,
        },
    }
