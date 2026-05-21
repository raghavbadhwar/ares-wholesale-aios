"""Local festive demand planning."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import InvoiceLineItem, ProductSKU, RiskLevel, StockRecord, Supplier
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_FESTIVE_DEMAND_LIMITATION = (
    "Local festive demand planning only; no external calendar, market-intelligence, forecasting model, "
    "supplier portal, or automatic purchase ordering was called."
)

LOCAL_FESTIVAL_MULTIPLIERS = {
    "diwali": 1.25,
    "navratri": 1.18,
    "eid": 1.15,
    "onam": 1.12,
    "holi": 1.15,
    "pongal": 1.12,
}


def prepare_festive_demand_plan(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    as_of: date,
    festival_name: str,
    festival_date: date,
    requested_by: str,
    planning_window_days: int = 42,
    history_window_days: int = 42,
    festival_multiplier: float | None = None,
    local_market_signal_multiplier: float = 1.0,
) -> dict[str, Any]:
    """Prepare local festive stocking recommendations for owner approval."""
    display_name = festival_name.strip().title()
    days_until = (festival_date - as_of).days
    multiplier = float(festival_multiplier or LOCAL_FESTIVAL_MULTIPLIERS.get(festival_name.strip().lower(), 1.15))
    audit = _audit(requested_by=requested_by, approval_required=False)
    calendar = {
        "festival_name": display_name,
        "festival_date": festival_date.isoformat(),
        "days_until_festival": days_until,
        "planning_window_days": planning_window_days,
        "history_window_days": history_window_days,
    }

    if days_until < 0 or days_until > planning_window_days:
        return {
            "mode": "local_contract_mock",
            "status": "not_in_planning_window",
            "calendar": calendar,
            "summary": _summary([], [], []),
            "recommendations": [],
            "missing_supplier_links": [],
            "unattributed_prior_year_lines": [],
            "audit": audit,
        }

    products = {product.id: product for product in repository.get_products()}
    stock_records = {record.sku_id: record for record in repository.get_stock_records()}
    suppliers = {supplier.id: supplier for supplier in repository.get_suppliers()}
    prior_units, unattributed_lines = _prior_year_units(
        repository=repository,
        products=products,
        festival_date=festival_date,
        history_window_days=history_window_days,
    )

    recommendations: list[dict[str, Any]] = []
    missing_supplier_links: list[dict[str, Any]] = []
    for sku_id, previous_year_units in prior_units.items():
        product = products[sku_id]
        supplier = suppliers.get(product.supplier_id or "")
        if supplier is None:
            missing_supplier_links.append({"sku_id": product.id, "sku_name": product.name, "code": "supplier_missing"})
            continue
        recommendation = _recommendation(
            product=product,
            stock=stock_records.get(product.id),
            supplier=supplier,
            previous_year_units=previous_year_units,
            festival_multiplier=multiplier,
            local_market_signal_multiplier=local_market_signal_multiplier,
            days_until_festival=days_until,
        )
        if recommendation is not None:
            recommendations.append(recommendation)

    recommendations.sort(key=lambda row: (float(row["suggested_order_quantity"]), row["sku_name"]), reverse=True)
    summary = _summary(recommendations, missing_supplier_links, unattributed_lines)
    audit = _audit(requested_by=requested_by, approval_required=bool(recommendations))
    if not recommendations:
        return {
            "mode": "local_contract_mock",
            "status": "no_festive_reorder_needed",
            "calendar": calendar,
            "summary": summary,
            "recommendations": [],
            "missing_supplier_links": missing_supplier_links,
            "unattributed_prior_year_lines": unattributed_lines,
            "audit": audit,
        }

    batch_id = f"festive_demand_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_festive_stocking_plan",
        proposed_action=f"Review {display_name} festive stocking plan",
        data={
            "batch_id": batch_id,
            "festival": calendar,
            "summary": summary,
            "recommendations": recommendations,
            "missing_supplier_links": missing_supplier_links,
            "unattributed_prior_year_lines": unattributed_lines,
            "mode": "local_contract_mock",
        },
        reason="Festive stocking recommendations can create purchase commitments and overstock risk; owner approval is required first.",
        source="festive_demand",
        confidence=0.82,
        risk_level=RiskLevel.high,
        dedupe_key=f"festive_demand:{client_id}:{display_name}:{festival_date.isoformat()}:{batch_id}",
    )
    return {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "calendar": calendar,
        "summary": summary,
        "recommendations": recommendations,
        "missing_supplier_links": missing_supplier_links,
        "unattributed_prior_year_lines": unattributed_lines,
        "audit": audit,
    }


def _prior_year_units(
    *,
    repository: BusinessRepository,
    products: dict[str, ProductSKU],
    festival_date: date,
    history_window_days: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    prior_festival_date = festival_date.replace(year=festival_date.year - 1)
    window_start = prior_festival_date - timedelta(days=max(0, history_window_days))
    totals: dict[str, float] = {}
    unattributed_lines: list[dict[str, Any]] = []
    for invoice in repository.get_invoices():
        if invoice.date is None or not (window_start <= invoice.date <= prior_festival_date):
            continue
        for line in invoice.line_items:
            sku_id = line.sku_id or ""
            if sku_id not in products:
                unattributed_lines.append(_unattributed_line(invoice_id=invoice.id, line=line))
                continue
            totals[sku_id] = round(totals.get(sku_id, 0.0) + float(line.quantity or 0), 2)
    return totals, unattributed_lines


def _recommendation(
    *,
    product: ProductSKU,
    stock: StockRecord | None,
    supplier: Supplier,
    previous_year_units: float,
    festival_multiplier: float,
    local_market_signal_multiplier: float,
    days_until_festival: int,
) -> dict[str, Any] | None:
    current_stock = float(stock.current_stock if stock else product.current_stock)
    sales_velocity = float(stock.sales_velocity or 0) if stock else 0.0
    lead_time_days = int(supplier.lead_time_days or 0)
    projected_units = round(previous_year_units * festival_multiplier * local_market_signal_multiplier, 2)
    lead_time_buffer = round(sales_velocity * lead_time_days, 2)
    suggested_quantity = round(max(projected_units + lead_time_buffer - current_stock, 0.0), 2)
    if suggested_quantity <= 0:
        return None
    return {
        "sku_id": product.id,
        "sku_name": product.name,
        "supplier_id": supplier.id,
        "supplier_name": supplier.name,
        "previous_year_units": round(previous_year_units, 2),
        "current_stock": round(current_stock, 2),
        "sales_velocity_per_day": round(sales_velocity, 2),
        "supplier_lead_time_days": lead_time_days,
        "festival_multiplier": round(festival_multiplier, 2),
        "local_market_signal_multiplier": round(local_market_signal_multiplier, 2),
        "projected_festive_units": projected_units,
        "lead_time_buffer_units": lead_time_buffer,
        "suggested_order_quantity": suggested_quantity,
        "estimated_purchase_value": round(suggested_quantity * float(product.buying_price or 0), 2),
        "priority": "urgent_pre_festival" if days_until_festival <= 21 else "six_week_replenishment",
    }


def _summary(
    recommendations: list[dict[str, Any]],
    missing_supplier_links: list[dict[str, Any]],
    unattributed_lines: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "recommended_skus": len(recommendations),
        "suggested_units": round(sum(float(row["suggested_order_quantity"]) for row in recommendations), 2),
        "estimated_purchase_value": round(sum(float(row["estimated_purchase_value"]) for row in recommendations), 2),
        "missing_supplier_links": len(missing_supplier_links),
        "unattributed_prior_year_lines": len(unattributed_lines),
    }


def _audit(*, requested_by: str, approval_required: bool) -> dict[str, Any]:
    return {
        "requested_by": requested_by,
        "approval_required": approval_required,
        "external_calendar_called": False,
        "external_market_intelligence_called": False,
        "demand_forecasting_model_called": False,
        "purchase_order_placed": False,
        "limitation": LOCAL_FESTIVE_DEMAND_LIMITATION,
    }


def _unattributed_line(*, invoice_id: str, line: InvoiceLineItem) -> dict[str, Any]:
    return {
        "invoice_id": invoice_id,
        "sku_id": line.sku_id,
        "description": line.description,
        "quantity": float(line.quantity or 0),
        "code": "sku_missing",
    }
