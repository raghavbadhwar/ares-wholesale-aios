"""Local GRN and three-way purchase matching surface."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import GoodsReceiptNote, PurchaseInvoice, PurchaseOrder, PurchaseOrderLine, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_GRN_LIMITATION = "Local GRN three-way match only; no warehouse, supplier, or accounting integration was called."


def _find_purchase_order(repository: BusinessRepository, purchase_order_id: str) -> PurchaseOrder:
    for order in repository.get_purchase_orders():
        if order.id == purchase_order_id:
            return order
    raise KeyError(f"Purchase order not found: {purchase_order_id}")


def _find_purchase_invoice(repository: BusinessRepository, purchase_invoice_id: str) -> PurchaseInvoice:
    for invoice in repository.get_purchase_invoices():
        if invoice.id == purchase_invoice_id:
            return invoice
    raise KeyError(f"Purchase invoice not found: {purchase_invoice_id}")


def _find_grn(repository: BusinessRepository, grn_id: str) -> GoodsReceiptNote:
    for receipt in repository.get_goods_receipt_notes():
        if receipt.id == grn_id:
            return receipt
    raise KeyError(f"Goods receipt note not found: {grn_id}")


def _line_by_sku(lines: list[PurchaseOrderLine]) -> dict[str, PurchaseOrderLine]:
    return {line.sku_id: line for line in lines}


def _received_by_sku(receipt: GoodsReceiptNote) -> dict[str, float]:
    quantities: dict[str, float] = {}
    for line in receipt.lines:
        quantities[line.sku_id] = round(quantities.get(line.sku_id, 0.0) + float(line.quantity_received), 2)
    return quantities


def _po_value(order: PurchaseOrder) -> float:
    return round(sum(float(line.quantity) * float(line.unit_cost) for line in order.lines), 2)


def reconcile_grn_three_way_match(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    purchase_order_id: str,
    purchase_invoice_id: str,
    grn_id: str,
    requested_by: str,
) -> dict[str, Any]:
    """Compare purchase order, supplier invoice, and goods receipt quantities/rates."""
    purchase_order = _find_purchase_order(repository, purchase_order_id)
    purchase_invoice = _find_purchase_invoice(repository, purchase_invoice_id)
    receipt = _find_grn(repository, grn_id)
    invoice_lines = _line_by_sku(purchase_invoice.line_items)
    received = _received_by_sku(receipt)
    matched_lines: list[dict[str, Any]] = []
    quantity_mismatches: list[dict[str, Any]] = []
    rate_mismatches: list[dict[str, Any]] = []
    missing_receipts: list[dict[str, Any]] = []

    for po_line in purchase_order.lines:
        invoice_line = invoice_lines.get(po_line.sku_id)
        invoiced_quantity = float(invoice_line.quantity) if invoice_line else 0.0
        invoiced_unit_cost = float(invoice_line.unit_cost) if invoice_line else 0.0
        received_quantity = float(received.get(po_line.sku_id, 0.0))
        ordered_quantity = float(po_line.quantity)
        ordered_unit_cost = float(po_line.unit_cost)
        receipt_missing = received_quantity <= 0
        if not receipt_missing and (ordered_quantity != invoiced_quantity or ordered_quantity != received_quantity):
            quantity_mismatches.append(
                {
                    "sku_id": po_line.sku_id,
                    "ordered_quantity": ordered_quantity,
                    "invoiced_quantity": invoiced_quantity,
                    "received_quantity": received_quantity,
                }
            )
        if invoiced_quantity > 0 and ordered_unit_cost != invoiced_unit_cost:
            rate_mismatches.append(
                {
                    "sku_id": po_line.sku_id,
                    "ordered_unit_cost": ordered_unit_cost,
                    "invoiced_unit_cost": invoiced_unit_cost,
                }
            )
        if receipt_missing:
            missing_receipts.append(
                {
                    "sku_id": po_line.sku_id,
                    "ordered_quantity": ordered_quantity,
                    "invoiced_quantity": invoiced_quantity,
                    "received_quantity": received_quantity,
                }
            )
        if ordered_quantity == invoiced_quantity == received_quantity and ordered_unit_cost == invoiced_unit_cost:
            matched_lines.append(
                {
                    "sku_id": po_line.sku_id,
                    "description": po_line.description,
                    "quantity": ordered_quantity,
                    "unit_cost": ordered_unit_cost,
                    "line_value": round(ordered_quantity * ordered_unit_cost, 2),
                }
            )

    summary = {
        "matched_lines": len(matched_lines),
        "quantity_mismatches": len(quantity_mismatches),
        "rate_mismatches": len(rate_mismatches),
        "missing_receipts": len(missing_receipts),
        "total_po_value": _po_value(purchase_order),
        "total_invoice_value": round(float(purchase_invoice.taxable_value), 2),
    }
    status = "needs_review" if quantity_mismatches or rate_mismatches or missing_receipts else "approval_required"
    audit = {
        "requested_by": requested_by,
        "approval_required": True,
        "external_inventory_or_accounting_write_performed": False,
        "limitation": LOCAL_GRN_LIMITATION,
    }
    batch_id = f"grn_match_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_grn_three_way_match",
        proposed_action=f"Review GRN three-way match for PO {purchase_order.order_number}",
        data={
            "batch_id": batch_id,
            "purchase_order_id": purchase_order_id,
            "purchase_invoice_id": purchase_invoice_id,
            "grn_id": grn_id,
            "summary": summary,
            "matched_lines": matched_lines,
            "quantity_mismatches": quantity_mismatches,
            "rate_mismatches": rate_mismatches,
            "missing_receipts": missing_receipts,
            "mode": "local_contract_mock",
        },
        reason="Goods receipts and supplier invoice matching affect stock and payable accuracy; owner/accountant review is required first.",
        source="grn_matching",
        confidence=0.9 if status == "approval_required" else 0.72,
        risk_level=RiskLevel.medium,
        dedupe_key=f"grn_match:{client_id}:{purchase_order_id}:{purchase_invoice_id}:{grn_id}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": status,
        "approval_id": approval.id,
        "summary": summary,
        "matched_lines": matched_lines,
        "quantity_mismatches": quantity_mismatches,
        "rate_mismatches": rate_mismatches,
        "missing_receipts": missing_receipts,
        "audit": audit,
    }
