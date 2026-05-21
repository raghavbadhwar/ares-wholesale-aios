from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import (
    GoodsReceiptNote,
    GoodsReceiptNoteLine,
    PurchaseInvoice,
    PurchaseOrder,
    PurchaseOrderLine,
    Supplier,
)
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.grn_matching import reconcile_grn_three_way_match


def test_should_match_purchase_order_invoice_and_grn_with_approval_audit() -> None:
    repo = InMemoryRepository.from_records(
        suppliers=[Supplier(id="sup_soap", name="Soap Principal", gstin="27PRINC1234F1Z5")],
        purchase_orders=[
            PurchaseOrder(
                id="po_1",
                supplier_id="sup_soap",
                order_number="PO-1",
                order_date=date(2026, 5, 10),
                lines=[
                    PurchaseOrderLine(sku_id="sku_soap", description="Soap Case", quantity=10, unit_cost=1000),
                ],
            )
        ],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                supplier_gstin="27PRINC1234F1Z5",
                purchase_order_id="po_1",
                invoice_number="PUR-1",
                date=date(2026, 5, 12),
                taxable_value=10000,
                tax_amount=1800,
                line_items=[
                    PurchaseOrderLine(sku_id="sku_soap", description="Soap Case", quantity=10, unit_cost=1000),
                ],
            )
        ],
        goods_receipt_notes=[
            GoodsReceiptNote(
                id="grn_1",
                supplier_id="sup_soap",
                purchase_order_id="po_1",
                received_on=date(2026, 5, 13),
                lines=[GoodsReceiptNoteLine(sku_id="sku_soap", description="Soap Case", quantity_received=10)],
            )
        ],
    )
    approvals = ApprovalService(repo)

    result = reconcile_grn_three_way_match(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        purchase_order_id="po_1",
        purchase_invoice_id="pinv_1",
        grn_id="grn_1",
        requested_by="warehouse_manager",
    )

    assert approvals.requires_approval("review_grn_three_way_match") is True
    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "approval_required"
    assert result["summary"] == {
        "matched_lines": 1,
        "quantity_mismatches": 0,
        "rate_mismatches": 0,
        "missing_receipts": 0,
        "total_po_value": 10000.0,
        "total_invoice_value": 10000.0,
    }
    assert result["matched_lines"][0]["sku_id"] == "sku_soap"
    assert result["audit"]["external_inventory_or_accounting_write_performed"] is False
    assert result["audit"]["limitation"] == "Local GRN three-way match only; no warehouse, supplier, or accounting integration was called."

    approval = repo.list_pending_approvals()[0]
    assert approval.type == "review_grn_three_way_match"
    assert approval.data["purchase_order_id"] == "po_1"
    assert approval.data["summary"] == result["summary"]


def test_should_surface_quantity_rate_and_missing_receipt_mismatches() -> None:
    repo = InMemoryRepository.from_records(
        suppliers=[Supplier(id="sup_soap", name="Soap Principal")],
        purchase_orders=[
            PurchaseOrder(
                id="po_1",
                supplier_id="sup_soap",
                order_number="PO-1",
                order_date=date(2026, 5, 10),
                lines=[
                    PurchaseOrderLine(sku_id="sku_soap", description="Soap Case", quantity=10, unit_cost=1000),
                    PurchaseOrderLine(sku_id="sku_shampoo", description="Shampoo Case", quantity=5, unit_cost=2000),
                ],
            )
        ],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PUR-1",
                date=date(2026, 5, 12),
                taxable_value=20500,
                tax_amount=3690,
                purchase_order_id="po_1",
                line_items=[
                    PurchaseOrderLine(sku_id="sku_soap", description="Soap Case", quantity=8, unit_cost=1050),
                    PurchaseOrderLine(sku_id="sku_shampoo", description="Shampoo Case", quantity=5, unit_cost=2000),
                ],
            )
        ],
        goods_receipt_notes=[
            GoodsReceiptNote(
                id="grn_1",
                supplier_id="sup_soap",
                purchase_order_id="po_1",
                received_on=date(2026, 5, 13),
                lines=[GoodsReceiptNoteLine(sku_id="sku_soap", description="Soap Case", quantity_received=8)],
            )
        ],
    )

    result = reconcile_grn_three_way_match(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        purchase_order_id="po_1",
        purchase_invoice_id="pinv_1",
        grn_id="grn_1",
        requested_by="warehouse_manager",
    )

    assert result["status"] == "needs_review"
    assert result["summary"]["quantity_mismatches"] == 1
    assert result["summary"]["rate_mismatches"] == 1
    assert result["summary"]["missing_receipts"] == 1
    assert result["quantity_mismatches"] == [
        {"sku_id": "sku_soap", "ordered_quantity": 10.0, "invoiced_quantity": 8.0, "received_quantity": 8.0}
    ]
    assert result["rate_mismatches"] == [
        {"sku_id": "sku_soap", "ordered_unit_cost": 1000.0, "invoiced_unit_cost": 1050.0}
    ]
    assert result["missing_receipts"] == [
        {"sku_id": "sku_shampoo", "ordered_quantity": 5.0, "invoiced_quantity": 5.0, "received_quantity": 0.0}
    ]


def test_should_persist_purchase_orders_and_grns_for_local_matching(tmp_path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    repo.upsert_purchase_order(
        PurchaseOrder(
            id="po_1",
            supplier_id="sup_soap",
            order_number="PO-1",
            order_date=date(2026, 5, 10),
            lines=[PurchaseOrderLine(sku_id="sku_soap", description="Soap Case", quantity=10, unit_cost=1000)],
        )
    )
    repo.upsert_goods_receipt_note(
        GoodsReceiptNote(
            id="grn_1",
            supplier_id="sup_soap",
            purchase_order_id="po_1",
            received_on=date(2026, 5, 13),
            lines=[GoodsReceiptNoteLine(sku_id="sku_soap", description="Soap Case", quantity_received=10)],
        )
    )

    reloaded = JsonClientRepository(tmp_path / "data")

    assert reloaded.get_purchase_orders()[0].order_number == "PO-1"
    assert reloaded.get_goods_receipt_notes()[0].purchase_order_id == "po_1"
