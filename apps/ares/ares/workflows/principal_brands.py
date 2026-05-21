"""Local principal and brand management review surface."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Brand, Principal, ProductSKU, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_PRINCIPAL_BRAND_LIMITATION = "Local principal/brand management surface only; no live principal, distributor, or ERP integration was called."


def _computed_margin_percent(product: ProductSKU) -> float | None:
    if product.buying_price is None or product.selling_price is None or product.buying_price <= 0:
        return product.margin
    return round(((float(product.selling_price) - float(product.buying_price)) / float(product.buying_price)) * 100, 2)


def _product_payload(product: ProductSKU) -> dict[str, Any]:
    return {
        "sku_id": product.id,
        "name": product.name,
        "brand_id": product.brand_id,
        "principal_id": product.principal_id,
        "current_stock": float(product.current_stock),
        "reorder_level": float(product.reorder_level),
        "low_stock": product.current_stock < product.reorder_level,
        "computed_margin_percent": _computed_margin_percent(product),
    }


def _brand_payload(brand: Brand) -> dict[str, Any]:
    return {
        "brand_id": brand.id,
        "brand_name": brand.name,
        "category": brand.category,
        "default_margin_percent": brand.default_margin_percent,
        "scheme_notes": brand.scheme_notes,
        "status": brand.status,
    }


def _missing_link_rows(products: list[ProductSKU], principals: dict[str, Principal], brands: dict[str, Brand]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for product in products:
        if not product.principal_id and not product.brand_id:
            rows.append({"sku_id": product.id, "name": product.name, "code": "principal_or_brand_missing"})
            continue
        if product.principal_id and product.principal_id not in principals:
            rows.append({"sku_id": product.id, "name": product.name, "code": "principal_missing"})
        if product.brand_id and product.brand_id not in brands:
            rows.append({"sku_id": product.id, "name": product.name, "code": "brand_missing"})
    return rows


def prepare_principal_brand_review(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare an approval-gated local principal/brand portfolio review."""
    principals = {principal.id: principal for principal in repository.get_principals()}
    brands = {brand.id: brand for brand in repository.get_brands()}
    products = repository.get_products()
    missing_links = _missing_link_rows(products, principals, brands)
    principal_rows: list[dict[str, Any]] = []

    for principal in principals.values():
        principal_brands = [brand for brand in brands.values() if brand.principal_id == principal.id]
        principal_products = [product for product in products if product.principal_id == principal.id]
        principal_rows.append(
            {
                "principal_id": principal.id,
                "principal_name": principal.name,
                "gstin": principal.gstin,
                "payment_terms": principal.payment_terms,
                "brands": [_brand_payload(brand) for brand in principal_brands],
                "products": [_product_payload(product) for product in principal_products],
            }
        )

    linked_products = [
        product
        for product in products
        if product.principal_id in principals and product.brand_id in brands
    ]
    summary = {
        "principals": len(principals),
        "brands": len(brands),
        "products_linked": len(linked_products),
        "low_stock_products": sum(1 for product in linked_products if product.current_stock < product.reorder_level),
        "missing_links": len({row["sku_id"] for row in missing_links}),
    }
    status = "needs_review" if missing_links else "approval_required"
    audit = {
        "requested_by": requested_by,
        "approval_required": True,
        "external_principal_sync_performed": False,
        "limitation": LOCAL_PRINCIPAL_BRAND_LIMITATION,
    }
    batch_id = f"principal_brand_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_principal_brand_plan",
        proposed_action="Review local principal and brand portfolio map",
        data={
            "batch_id": batch_id,
            "summary": summary,
            "principals": principal_rows,
            "missing_links": missing_links,
            "mode": "local_contract_mock",
        },
        reason="Principal, brand, margin, and terms records influence purchasing and sales decisions; owner review is required first.",
        source="principal_brands",
        confidence=0.9 if not missing_links else 0.7,
        risk_level=RiskLevel.medium,
        dedupe_key=f"principal_brand:{client_id}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": status,
        "approval_id": approval.id,
        "summary": summary,
        "principals": principal_rows,
        "missing_links": missing_links,
        "audit": audit,
    }
