from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Invoice, InvoiceLineItem, ProductSKU, StockRecord, Supplier
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.festive_demand import LOCAL_FESTIVE_DEMAND_LIMITATION, prepare_festive_demand_plan


def test_should_prepare_approval_gated_festive_demand_plan_from_prior_year_sales_and_stock() -> None:
    repo = InMemoryRepository.from_records(
        suppliers=[Supplier(id="sup_soap", name="Soap Supplier", lead_time_days=7)],
        products=[ProductSKU(id="sku_soap", name="Soap Case", supplier_id="sup_soap", current_stock=10, buying_price=100)],
        stock_records=[StockRecord(sku_id="sku_soap", name="Soap Case", current_stock=10, reorder_level=20, sales_velocity=2)],
        invoices=[
            Invoice(
                id="inv_py",
                invoice_number="PY-1",
                date=date(2025, 10, 20),
                amount=10000,
                status="paid",
                line_items=[
                    InvoiceLineItem(
                        sku_id="sku_soap",
                        description="Soap Case",
                        quantity=100,
                        taxable_value=10000,
                    )
                ],
            )
        ],
    )
    approvals = ApprovalService(repo)

    plan = prepare_festive_demand_plan(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        as_of=date(2026, 9, 27),
        festival_name="Diwali",
        festival_date=date(2026, 11, 8),
        requested_by="owner",
    )

    assert plan["mode"] == "local_contract_mock"
    assert plan["status"] == "approval_required"
    assert plan["calendar"]["festival_name"] == "Diwali"
    assert plan["calendar"]["days_until_festival"] == 42
    assert plan["summary"] == {
        "recommended_skus": 1,
        "suggested_units": 129.0,
        "estimated_purchase_value": 12900.0,
        "missing_supplier_links": 0,
        "unattributed_prior_year_lines": 0,
    }
    assert plan["recommendations"] == [
        {
            "sku_id": "sku_soap",
            "sku_name": "Soap Case",
            "supplier_id": "sup_soap",
            "supplier_name": "Soap Supplier",
            "previous_year_units": 100.0,
            "current_stock": 10.0,
            "sales_velocity_per_day": 2.0,
            "supplier_lead_time_days": 7,
            "festival_multiplier": 1.25,
            "local_market_signal_multiplier": 1.0,
            "projected_festive_units": 125.0,
            "lead_time_buffer_units": 14.0,
            "suggested_order_quantity": 129.0,
            "estimated_purchase_value": 12900.0,
            "priority": "six_week_replenishment",
        }
    ]
    assert plan["audit"] == {
        "requested_by": "owner",
        "approval_required": True,
        "external_calendar_called": False,
        "external_market_intelligence_called": False,
        "demand_forecasting_model_called": False,
        "purchase_order_placed": False,
        "limitation": LOCAL_FESTIVE_DEMAND_LIMITATION,
    }
    assert repo.list_pending_approvals()[0].type == "review_festive_stocking_plan"


def test_should_return_noop_when_festival_is_outside_six_week_window() -> None:
    repo = InMemoryRepository()

    plan = prepare_festive_demand_plan(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        as_of=date(2026, 8, 1),
        festival_name="Diwali",
        festival_date=date(2026, 11, 8),
        requested_by="owner",
    )

    assert plan["mode"] == "local_contract_mock"
    assert plan["status"] == "not_in_planning_window"
    assert plan["summary"]["recommended_skus"] == 0
    assert plan["audit"]["external_calendar_called"] is False
    assert plan["audit"]["limitation"] == LOCAL_FESTIVE_DEMAND_LIMITATION
    assert repo.list_pending_approvals() == []
