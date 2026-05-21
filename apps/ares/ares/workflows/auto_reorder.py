"""Local auto-reorder intelligence."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ProductSKU, RiskLevel, StockRecord, Supplier
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_AUTO_REORDER_LIMITATION = (
    "Local auto-reorder intelligence only; no supplier integration or automatic purchase order placement was performed."
)


def _stock_by_sku(repository: BusinessRepository) -> dict[str, StockRecord]:
    return {record.sku_id: record for record in repository.get_stock_records()}


def _supplier_by_id(repository: BusinessRepository) -> dict[str, Supplier]:
    return {supplier.id: supplier for supplier in repository.get_suppliers()}


def _current_stock(product: ProductSKU, stock: StockRecord | None) -> float:
    return float(stock.current_stock if stock else product.current_stock)


def _reorder_level(product: ProductSKU, stock: StockRecord | None) -> float:
    return float(stock.reorder_level if stock else product.reorder_level)


def _sales_velocity(stock: StockRecord | None) -> float:
    return float(stock.sales_velocity or 0) if stock else 0.0


def _suggested_quantity(*, current_stock: float, reorder_level: float, sales_velocity: float, lead_time_days: int, coverage_days: int) -> float:
    threshold_gap = max(reorder_level - current_stock, 0.0)
    velocity_need = max((sales_velocity * (lead_time_days + coverage_days)) - current_stock, 0.0)
    return round(max(threshold_gap, velocity_need), 2)


def _priority(*, current_stock: float, reorder_level: float, sales_velocity: float, lead_time_days: int) -> str:
    if current_stock <= 0:
        return "stockout"
    if sales_velocity > 0 and current_stock <= sales_velocity * lead_time_days:
        return "urgent"
    if current_stock < reorder_level:
        return "reorder"
    return "planned"


def _recommendation(
    *,
    product: ProductSKU,
    stock: StockRecord | None,
    supplier: Supplier,
    coverage_days: int,
) -> dict[str, Any] | None:
    current_stock = _current_stock(product, stock)
    reorder_level = _reorder_level(product, stock)
    sales_velocity = _sales_velocity(stock)
    lead_time_days = int(supplier.lead_time_days or 0)
    quantity = _suggested_quantity(
        current_stock=current_stock,
        reorder_level=reorder_level,
        sales_velocity=sales_velocity,
        lead_time_days=lead_time_days,
        coverage_days=coverage_days,
    )
    if quantity <= 0:
        return None
    return {
        "sku_id": product.id,
        "sku_name": product.name,
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "current_stock": current_stock,
        "reorder_level": reorder_level,
        "sales_velocity_per_day": sales_velocity,
        "lead_time_days": lead_time_days,
        "coverage_days": coverage_days,
        "suggested_order_quantity": quantity,
        "estimated_purchase_value": round(quantity * float(product.buying_price or 0), 2),
        "priority": _priority(
            current_stock=current_stock,
            reorder_level=reorder_level,
            sales_velocity=sales_velocity,
            lead_time_days=lead_time_days,
        ),
    }


def prepare_auto_reorder_plan(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    as_of: date,
    coverage_days: int,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare local replenishment recommendations for approval before purchase ordering."""
    stock_records = _stock_by_sku(repository)
    suppliers = _supplier_by_id(repository)
    recommendations: list[dict[str, Any]] = []
    missing_supplier_links: list[dict[str, Any]] = []

    for product in repository.get_products():
        stock = stock_records.get(product.id)
        supplier = suppliers.get(product.supplier_id or "")
        current_stock = _current_stock(product, stock)
        reorder_level = _reorder_level(product, stock)
        sales_velocity = _sales_velocity(stock)
        needs_reorder_signal = current_stock < reorder_level or (sales_velocity > 0 and current_stock < sales_velocity * coverage_days)
        if supplier is None:
            if needs_reorder_signal:
                missing_supplier_links.append({"sku_id": product.id, "sku_name": product.name, "code": "supplier_missing"})
            continue
        row = _recommendation(product=product, stock=stock, supplier=supplier, coverage_days=coverage_days)
        if row is not None:
            recommendations.append(row)

    priority_rank = {"stockout": 0, "urgent": 1, "reorder": 2, "planned": 3}
    recommendations.sort(key=lambda row: (priority_rank[row["priority"]], row["supplier_name"], row["sku_name"]))
    summary = {
        "reorder_skus": len(recommendations),
        "suggested_units": round(sum(float(row["suggested_order_quantity"]) for row in recommendations), 2),
        "estimated_purchase_value": round(sum(float(row["estimated_purchase_value"]) for row in recommendations), 2),
        "missing_supplier_links": len(missing_supplier_links),
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": bool(recommendations),
        "external_supplier_portal_called": False,
        "purchase_order_placed": False,
        "limitation": LOCAL_AUTO_REORDER_LIMITATION,
    }
    if not recommendations:
        return {
            "mode": "local_contract_mock",
            "status": "no_reorder_needed",
            "as_of": as_of.isoformat(),
            "summary": summary,
            "recommendations": [],
            "missing_supplier_links": missing_supplier_links,
            "audit": audit,
        }

    batch_id = f"auto_reorder_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="place_purchase_order",
        proposed_action=f"Review local auto-reorder plan for {as_of.isoformat()}",
        data={
            "batch_id": batch_id,
            "as_of": as_of.isoformat(),
            "coverage_days": coverage_days,
            "summary": summary,
            "recommendations": recommendations,
            "missing_supplier_links": missing_supplier_links,
            "mode": "local_contract_mock",
        },
        reason="Auto-reorder recommendations can create purchase commitments; owner approval is required first.",
        source="auto_reorder",
        confidence=0.84,
        risk_level=RiskLevel.high,
        dedupe_key=f"auto_reorder:{client_id}:{as_of.isoformat()}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "as_of": as_of.isoformat(),
        "summary": summary,
        "recommendations": recommendations,
        "missing_supplier_links": missing_supplier_links,
        "audit": audit,
    }
