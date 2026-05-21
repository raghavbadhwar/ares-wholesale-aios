from __future__ import annotations

from apps.ares.ares.data.models import Customer, Order, OrderItem, ProductSKU
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.gst_invoice import draft_gst_invoice


def test_draft_gst_invoice_builds_totals_for_priced_order() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_raj", name="Raj Traders", gstin="27ABCDE1234F1Z5", location="MH")],
        products=[
            ProductSKU(id="surf_excel", name="Surf Excel", selling_price=1200),
            ProductSKU(id="vim_bar", name="Vim Bar", selling_price=300),
        ],
    )
    order = Order(
        id="ord_1",
        customer_id="cust_raj",
        items=[
            OrderItem(sku_id="surf_excel", name="Surf Excel", quantity=2, unit="carton"),
            OrderItem(sku_id="vim_bar", name="Vim Bar", quantity=3, unit="box"),
        ],
    )

    draft = draft_gst_invoice(order, repo, seller_gstin="27AACCA1234A1Z9", seller_state_code="27")

    assert draft["ok"] is True
    assert draft["validation_errors"] == []
    assert draft["customer_gstin"] == "27ABCDE1234F1Z5"
    assert draft["tax_mode"] == "intra_state"
    assert draft["totals"]["taxable_value"] == 3300.0
    assert draft["totals"]["tax_amount"] == 594.0
    assert draft["totals"]["grand_total"] == 3894.0
    assert draft["lines"][0]["line_total"] == 2400.0
    assert draft["lines"][1]["line_total"] == 900.0


def test_draft_gst_invoice_returns_validation_errors_for_missing_compliance_data() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_raj", name="Raj Traders")],
        products=[ProductSKU(id="surf_excel", name="Surf Excel")],
    )
    order = Order(
        id="ord_1",
        customer_id="cust_raj",
        items=[OrderItem(sku_id="surf_excel", name="Surf Excel", quantity=2, unit="carton")],
    )

    draft = draft_gst_invoice(order, repo, seller_gstin="", seller_state_code="27")

    assert draft["ok"] is False
    assert "seller_gstin_missing" in draft["validation_errors"]
    assert "customer_gstin_missing" in draft["validation_errors"]
    assert "missing_selling_price:surf_excel" in draft["validation_errors"]


def test_draft_gst_invoice_uses_igst_for_inter_state_customer() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_delhi", name="Delhi Retail", gstin="07ABCDE1234F1Z5", location="DL")],
        products=[ProductSKU(id="surf_excel", name="Surf Excel", selling_price=1000)],
    )
    order = Order(
        id="ord_1",
        customer_id="cust_delhi",
        items=[OrderItem(sku_id="surf_excel", name="Surf Excel", quantity=1, unit="carton")],
    )

    draft = draft_gst_invoice(order, repo, seller_gstin="27AACCA1234A1Z9", seller_state_code="27")

    assert draft["ok"] is True
    assert draft["tax_mode"] == "inter_state"
    assert draft["totals"]["igst"] == 180.0
    assert draft["totals"]["cgst"] == 0.0
    assert draft["totals"]["sgst"] == 0.0
