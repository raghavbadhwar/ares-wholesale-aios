"""Local ONDC seller-node contract surfaces."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, Order, OrderItem, ProductSKU, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_ONDC_SELLER_LIMITATION = (
    "Local ONDC seller-node contract only; no ONDC network, catalogue sync, stock commitment, "
    "logistics API, or order execution was called."
)


def prepare_ondc_catalogue_sync_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    seller_id: str,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare an approval-gated local ONDC catalogue sync contract."""
    items = [_catalogue_item(product) for product in repository.get_products()]
    summary = {
        "catalogue_items": len(items),
        "out_of_stock_items": sum(1 for item in items if item["available_quantity"] <= 0),
    }
    audit = _audit(requested_by=requested_by, approval_required=True)
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="sync_ondc_catalogue",
        proposed_action=f"Review ONDC catalogue contract for seller {seller_id}",
        data={
            "seller_id": seller_id,
            "summary": summary,
            "items": items,
            "mode": "local_contract_mock",
        },
        reason="ONDC catalogue sync can expose stock, prices, GST metadata, and fulfilment promises externally; owner approval is required first.",
        source="ondc_seller",
        confidence=0.82,
        risk_level=RiskLevel.high,
        dedupe_key=f"ondc_catalogue:{client_id}:{seller_id}:{uuid4().hex[:8]}",
    )
    result = {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "seller_id": seller_id,
        "summary": summary,
        "items": items,
        "audit": audit,
    }
    _save_log(repository, client_id=client_id, action_type="ondc_catalogue_sync_contract", status=result["status"], result=result, approval_id=approval.id)
    return result


def ingest_ondc_order_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    requested_by: str,
    ondc_order: dict[str, Any],
) -> dict[str, Any]:
    """Ingest an ONDC-shaped order into the local order queue without committing stock."""
    ondc_order_id = str(ondc_order["ondc_order_id"])
    audit = _audit(requested_by=requested_by, approval_required=False)
    existing = next((order for order in repository.list_orders() if order.source == "ondc_contract" and order.file_id == ondc_order_id), None)
    if existing is not None:
        result = {
            "mode": "local_contract_mock",
            "status": "duplicate_ignored",
            "order": existing.model_dump(mode="json"),
            "audit": audit,
        }
        _save_log(repository, client_id=client_id, action_type="ondc_order_contract", status=result["status"], result=result)
        return result

    order = repository.create_order(
        Order(
            id=f"ord_{uuid4().hex[:12]}",
            customer_id=ondc_order.get("buyer_id"),
            source="ondc_contract",
            raw_text=f"ONDC order {ondc_order_id}",
            file_id=ondc_order_id,
            items=[
                OrderItem(
                    sku_id=item.get("sku_id"),
                    name=item.get("name") or item.get("sku_id") or "ONDC item",
                    quantity=float(item.get("quantity", 0)),
                    unit=item.get("unit") or "unit",
                )
                for item in ondc_order.get("items", [])
            ],
            status="pending",
        )
    )
    audit = _audit(requested_by=requested_by, approval_required=True)
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="add_order_to_dispatch_queue",
        proposed_action=f"Review ONDC order {ondc_order_id} before dispatch queue",
        data={"order": order.model_dump(mode="json"), "mode": "local_contract_mock"},
        reason="ONDC orders can reserve stock and create GST/logistics obligations; local approval is required before dispatch commitment.",
        source="ondc_seller",
        confidence=0.82,
        risk_level=RiskLevel.high,
        dedupe_key=f"ondc_order:{client_id}:{ondc_order_id}",
    )
    result = {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "order": order.model_dump(mode="json"),
        "audit": audit,
    }
    _save_log(repository, client_id=client_id, action_type="ondc_order_contract", status=result["status"], result=result, approval_id=approval.id)
    return result


def _catalogue_item(product: ProductSKU) -> dict[str, Any]:
    return {
        "sku_id": product.id,
        "name": product.name,
        "category": product.category,
        "available_quantity": round(float(product.current_stock), 2),
        "unit": product.unit,
        "price": round(float(product.selling_price or 0), 2),
        "stock_commitment_required": False,
    }


def _audit(*, requested_by: str, approval_required: bool) -> dict[str, Any]:
    return {
        "requested_by": requested_by,
        "approval_required": approval_required,
        "ondc_network_called": False,
        "catalogue_synced": False,
        "stock_committed": False,
        "logistics_api_called": False,
        "order_execution_performed": False,
        "limitation": LOCAL_ONDC_SELLER_LIMITATION,
    }


def _save_log(
    repository: BusinessRepository,
    *,
    client_id: str,
    action_type: str,
    status: str,
    result: dict[str, Any],
    approval_id: str | None = None,
) -> None:
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_{uuid4().hex[:12]}",
            client_id=client_id,
            approval_id=approval_id,
            action_type=action_type,
            status=status,
            result={
                "status": status,
                "limitation": result["audit"]["limitation"],
                "ondc_network_called": result["audit"]["ondc_network_called"],
                "catalogue_synced": result["audit"]["catalogue_synced"],
                "stock_committed": result["audit"]["stock_committed"],
            },
        )
    )
