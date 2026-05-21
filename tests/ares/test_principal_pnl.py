from __future__ import annotations

from datetime import date

from apps.ares.ares.data.models import (
    Brand,
    InventoryBatch,
    Invoice,
    InvoiceLineItem,
    Principal,
    ProductSKU,
    SchemeClaim,
)
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.principal_pnl import build_principal_pnl


def test_should_build_principal_wise_pnl_with_margin_claim_and_stock_risk() -> None:
    repo = InMemoryRepository.from_records(
        principals=[
            Principal(id="pr_hul", name="HUL"),
            Principal(id="pr_pg", name="P&G"),
        ],
        brands=[
            Brand(id="br_surf", principal_id="pr_hul", name="Surf Excel"),
            Brand(id="br_ariel", principal_id="pr_pg", name="Ariel"),
        ],
        products=[
            ProductSKU(
                id="sku_surf",
                name="Surf Excel 1kg",
                principal_id="pr_hul",
                brand_id="br_surf",
                buying_price=80,
                selling_price=100,
                current_stock=50,
                reorder_level=20,
            ),
            ProductSKU(
                id="sku_ariel",
                name="Ariel 1kg",
                principal_id="pr_pg",
                brand_id="br_ariel",
                buying_price=90,
                selling_price=110,
                current_stock=4,
                reorder_level=10,
            ),
        ],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                date=date(2026, 5, 10),
                amount=1180,
                taxable_value=1000,
                tax_amount=180,
                line_items=[
                    InvoiceLineItem(sku_id="sku_surf", description="Surf Excel 1kg", quantity=10, taxable_value=1000),
                ],
            ),
            Invoice(
                id="inv_2",
                invoice_number="INV-2",
                date=date(2026, 5, 11),
                amount=550,
                taxable_value=550,
                tax_amount=0,
                line_items=[InvoiceLineItem(sku_id="sku_ariel", description="Ariel 1kg", quantity=5, taxable_value=550)],
            ),
        ],
        scheme_claims=[
            SchemeClaim(
                id="claim_1",
                scheme_id="scheme_surf",
                principal_id="pr_hul",
                invoice_id="inv_1",
                sku_id="sku_surf",
                claim_amount=50,
                status="approved",
            )
        ],
        inventory_batches=[
            InventoryBatch(id="batch_ariel", sku_id="sku_ariel", batch_code="A1", quantity=4),
        ],
    )

    report = build_principal_pnl(repository=repo, period="2026-05")

    assert report["mode"] == "local_contract_mock"
    assert report["summary"] == {
        "principals": 2,
        "revenue": 1550.0,
        "gross_margin": 300.0,
        "scheme_claims": 50.0,
        "low_stock_principals": 1,
    }
    assert report["principals"][0] == {
        "principal_id": "pr_hul",
        "principal_name": "HUL",
        "revenue": 1000.0,
        "estimated_cogs": 800.0,
        "gross_margin": 200.0,
        "gross_margin_percent": 20.0,
        "scheme_claims": 50.0,
        "net_margin_after_claims": 250.0,
        "low_stock_skus": [],
    }
    assert report["principals"][1]["principal_id"] == "pr_pg"
    assert report["principals"][1]["low_stock_skus"] == ["sku_ariel"]
    assert report["audit"]["external_accounting_close_performed"] is False
    assert report["audit"]["limitation"] == "Local principal-wise P&L analytics only; no ERP close, bank, or accounting integration was called."


def test_should_flag_unlinked_invoice_lines_as_unattributed_margin() -> None:
    repo = InMemoryRepository.from_records(
        products=[ProductSKU(id="sku_unknown", name="Unknown SKU", buying_price=50)],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                date=date(2026, 5, 10),
                amount=100,
                taxable_value=100,
                tax_amount=0,
                line_items=[InvoiceLineItem(sku_id="sku_unknown", description="Unknown SKU", quantity=1, taxable_value=100)],
            )
        ],
    )

    report = build_principal_pnl(repository=repo, period="2026-05")

    assert report["summary"]["principals"] == 0
    assert report["unattributed_lines"] == [
        {"invoice_id": "inv_1", "sku_id": "sku_unknown", "taxable_value": 100.0, "code": "principal_missing"}
    ]
