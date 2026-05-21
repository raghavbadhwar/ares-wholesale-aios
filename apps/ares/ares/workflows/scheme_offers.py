"""Local scheme and offer suggestion workflow."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Order, OrderItem, ProductSKU, RiskLevel, TradeScheme
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_SCHEME_OFFER_LIMITATION = (
    "Local scheme/offer suggestion only; no principal portal validation or automatic discount execution was performed."
)


def _find_product(repository: BusinessRepository, item: OrderItem) -> ProductSKU | None:
    normalized = item.name.strip().lower()
    for product in repository.get_products():
        if item.sku_id and product.id == item.sku_id:
            return product
        names = [product.name, *product.aliases]
        if any(name.strip().lower() == normalized for name in names if name):
            return product
    return None


def _active_schemes(repository: BusinessRepository, as_of: date) -> list[TradeScheme]:
    return [
        scheme
        for scheme in repository.get_trade_schemes()
        if scheme.status == "active" and scheme.start_date <= as_of <= scheme.end_date
    ]


def _matching_schemes(product: ProductSKU, schemes: list[TradeScheme]) -> list[TradeScheme]:
    rows = []
    for scheme in schemes:
        if scheme.principal_id != product.principal_id:
            continue
        if scheme.brand_id and scheme.brand_id != product.brand_id:
            continue
        rows.append(scheme)
    return rows


def _benefit_amount(scheme: TradeScheme, *, quantity: float, line_value: float) -> float:
    if scheme.payout_type == "percent":
        return round(line_value * (float(scheme.payout_value) / 100), 2)
    return round(quantity * float(scheme.payout_value), 2)


def _suggestion_for_item(product: ProductSKU, item: OrderItem, schemes: list[TradeScheme]) -> dict[str, Any] | None:
    if product.selling_price is None:
        return None
    quantity = float(item.quantity)
    line_value = round(quantity * float(product.selling_price), 2)
    candidates = [
        (scheme, _benefit_amount(scheme, quantity=quantity, line_value=line_value))
        for scheme in _matching_schemes(product, schemes)
    ]
    if not candidates:
        return None
    best_scheme, best_amount = max(candidates, key=lambda item: (item[1], item[0].name))
    if best_amount <= 0:
        return None
    return {
        "sku_id": product.id,
        "product_name": product.name,
        "quantity": quantity,
        "line_value": line_value,
        "scheme_id": best_scheme.id,
        "scheme_name": best_scheme.name,
        "benefit_type": best_scheme.payout_type,
        "benefit_value": float(best_scheme.payout_value),
        "suggested_discount_amount": best_amount,
    }


def prepare_scheme_offer_applications(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    order: Order,
    as_of: date,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare local scheme/offer suggestions for owner review before application."""
    schemes = _active_schemes(repository, as_of)
    suggestions: list[dict[str, Any]] = []
    unmatched_lines: list[dict[str, Any]] = []

    for item in order.items:
        product = _find_product(repository, item)
        if product is None:
            unmatched_lines.append({"sku_id": item.sku_id, "name": item.name, "code": "product_missing"})
            continue
        suggestion = _suggestion_for_item(product, item, schemes)
        if suggestion is not None:
            suggestions.append(suggestion)

    summary = {
        "eligible_lines": len(suggestions),
        "suggested_discount_amount": round(sum(float(row["suggested_discount_amount"]) for row in suggestions), 2),
        "unmatched_lines": len(unmatched_lines),
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": bool(suggestions),
        "external_principal_portal_called": False,
        "automatic_discount_posted": False,
        "limitation": LOCAL_SCHEME_OFFER_LIMITATION,
    }
    if not suggestions:
        return {
            "mode": "local_contract_mock",
            "status": "no_applicable_schemes",
            "order_id": order.id,
            "summary": summary,
            "suggestions": [],
            "unmatched_lines": unmatched_lines,
            "audit": audit,
        }

    batch_id = f"scheme_offer_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="apply_scheme_offer",
        proposed_action=f"Review local scheme/offer suggestions for order {order.id}",
        data={
            "batch_id": batch_id,
            "order_id": order.id,
            "summary": summary,
            "suggestions": suggestions,
            "unmatched_lines": unmatched_lines,
            "mode": "local_contract_mock",
        },
        reason="Scheme/offer application affects invoice pricing and principal claims; owner review is required first.",
        source="scheme_offers",
        confidence=0.82,
        risk_level=RiskLevel.medium,
        dedupe_key=f"scheme_offer:{client_id}:{order.id}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "order_id": order.id,
        "summary": summary,
        "suggestions": suggestions,
        "unmatched_lines": unmatched_lines,
        "audit": audit,
    }
