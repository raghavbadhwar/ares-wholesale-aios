from __future__ import annotations

from datetime import date

from apps.ares.ares.data.models import InventoryBatch, Invoice, InvoiceLineItem, ProductSKU
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.sku_performance import build_sku_performance_intelligence


def test_should_rank_sku_performance_with_margin_stock_and_expiry_signals() -> None:
    repo = InMemoryRepository.from_records(
        products=[
            ProductSKU(id="sku_fast", name="Fast Soap", buying_price=70, selling_price=100, current_stock=3, reorder_level=10),
            ProductSKU(id="sku_slow", name="Slow Oil", buying_price=80, selling_price=120, current_stock=100, reorder_level=10),
        ],
        inventory_batches=[
            InventoryBatch(id="batch_fast", sku_id="sku_fast", batch_code="FAST-1", quantity=3, expiry_date=date(2026, 6, 5)),
            InventoryBatch(id="batch_slow", sku_id="sku_slow", batch_code="SLOW-1", quantity=100, expiry_date=date(2026, 12, 31)),
        ],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                date=date(2026, 5, 10),
                amount=2120,
                taxable_value=2120,
                tax_amount=0,
                line_items=[
                    InvoiceLineItem(sku_id="sku_fast", description="Fast Soap", quantity=20, taxable_value=2000),
                    InvoiceLineItem(sku_id="sku_slow", description="Slow Oil", quantity=1, taxable_value=120),
                    InvoiceLineItem(sku_id="sku_unknown", description="Unknown", quantity=1, taxable_value=50),
                ],
            )
        ],
    )

    report = build_sku_performance_intelligence(repository=repo, as_of=date(2026, 5, 21), lookback_days=90)

    assert report["mode"] == "local_contract_mock"
    assert report["summary"] == {
        "skus": 2,
        "units_sold": 21.0,
        "revenue": 2120.0,
        "gross_margin": 640.0,
        "low_stock_skus": 1,
        "expiring_batches": 1,
        "unattributed_lines": 1,
    }
    assert report["sku_performance"][0] == {
        "sku_id": "sku_fast",
        "sku_name": "Fast Soap",
        "units_sold": 20.0,
        "revenue": 2000.0,
        "estimated_cogs": 1400.0,
        "gross_margin": 600.0,
        "gross_margin_percent": 30.0,
        "current_stock": 3.0,
        "reorder_level": 10.0,
        "stock_status": "reorder_now",
        "expiring_batches": [{"batch_id": "batch_fast", "batch_code": "FAST-1", "expiry_date": "2026-06-05", "quantity": 3.0}],
        "recommended_action": "Reorder or prioritize replenishment before stockout.",
    }
    assert report["sku_performance"][1]["stock_status"] == "healthy"
    assert report["unattributed_lines"] == [
        {"invoice_id": "inv_1", "sku_id": "sku_unknown", "taxable_value": 50.0, "code": "sku_missing"}
    ]
    assert report["audit"] == {
        "predictive_demand_model_called": False,
        "external_market_intelligence_called": False,
        "limitation": "Local SKU performance intelligence only; no demand forecasting model or external market intelligence was called.",
    }


def test_should_return_zero_sku_performance_without_products() -> None:
    report = build_sku_performance_intelligence(repository=InMemoryRepository(), as_of=date(2026, 5, 21))

    assert report["summary"]["skus"] == 0
    assert report["sku_performance"] == []
