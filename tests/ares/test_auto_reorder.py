from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ProductSKU, StockRecord, Supplier
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.auto_reorder import prepare_auto_reorder_plan


def test_should_prepare_approval_gated_reorder_plan_from_stock_velocity_and_supplier_lead_time() -> None:
    repo = InMemoryRepository.from_records(
        suppliers=[Supplier(id="sup_soap", name="Soap Supplier", lead_time_days=7)],
        products=[
            ProductSKU(id="sku_soap", name="Soap Case", supplier_id="sup_soap", current_stock=5, reorder_level=20, buying_price=100),
            ProductSKU(id="sku_ok", name="Healthy SKU", supplier_id="sup_soap", current_stock=100, reorder_level=20, buying_price=50),
        ],
        stock_records=[
            StockRecord(sku_id="sku_soap", name="Soap Case", current_stock=5, reorder_level=20, sales_velocity=3),
            StockRecord(sku_id="sku_ok", name="Healthy SKU", current_stock=100, reorder_level=20, sales_velocity=1),
        ],
    )
    approvals = ApprovalService(repo)

    plan = prepare_auto_reorder_plan(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        as_of=date(2026, 5, 21),
        coverage_days=14,
        requested_by="owner",
    )

    assert plan["mode"] == "local_contract_mock"
    assert plan["status"] == "approval_required"
    assert plan["summary"] == {
        "reorder_skus": 1,
        "suggested_units": 58.0,
        "estimated_purchase_value": 5800.0,
        "missing_supplier_links": 0,
    }
    assert plan["recommendations"] == [
        {
            "sku_id": "sku_soap",
            "sku_name": "Soap Case",
            "supplier_id": "sup_soap",
            "supplier_name": "Soap Supplier",
            "current_stock": 5.0,
            "reorder_level": 20.0,
            "sales_velocity_per_day": 3.0,
            "lead_time_days": 7,
            "coverage_days": 14,
            "suggested_order_quantity": 58.0,
            "estimated_purchase_value": 5800.0,
            "priority": "urgent",
        }
    ]
    assert plan["audit"] == {
        "requested_by": "owner",
        "approval_required": True,
        "external_supplier_portal_called": False,
        "purchase_order_placed": False,
        "limitation": "Local auto-reorder intelligence only; no supplier integration or automatic purchase order placement was performed.",
    }
    assert repo.list_pending_approvals()[0].type == "place_purchase_order"


def test_should_return_noop_when_no_reorder_is_needed() -> None:
    repo = InMemoryRepository.from_records(
        products=[ProductSKU(id="sku_ok", name="Healthy SKU", current_stock=100, reorder_level=20, buying_price=50)],
        stock_records=[StockRecord(sku_id="sku_ok", name="Healthy SKU", current_stock=100, reorder_level=20, sales_velocity=1)],
    )

    plan = prepare_auto_reorder_plan(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        as_of=date(2026, 5, 21),
        coverage_days=14,
        requested_by="owner",
    )

    assert plan["status"] == "no_reorder_needed"
    assert plan["recommendations"] == []
    assert repo.list_pending_approvals() == []
