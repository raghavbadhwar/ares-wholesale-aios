"""Local e-way bill draft preparation contract."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, InvoiceLineItem, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_EWAY_BILL_LIMITATION = "Local e-way bill preparation contract only; no NIC/GSTN API was called."
EWAY_BILL_THRESHOLD = 50000.0


def _find_invoice(repository: BusinessRepository, invoice_id: str) -> Invoice:
    for invoice in repository.get_invoices():
        if invoice.id == invoice_id:
            return invoice
    raise KeyError(f"Invoice not found: {invoice_id}")


def _find_customer(repository: BusinessRepository, customer_id: str | None) -> Customer | None:
    if not customer_id:
        return None
    for customer in repository.get_customers():
        if customer.id == customer_id:
            return customer
    return None


def _line_items(invoice: Invoice) -> list[InvoiceLineItem]:
    if invoice.line_items:
        return invoice.line_items
    return [
        InvoiceLineItem(
            description="Invoice-level goods",
            hsn_code="unclassified",
            taxable_value=invoice.taxable_value or 0,
            quantity=0,
            unit="unit",
            gst_rate_percent=invoice.gst_rate_percent,
            igst_amount=invoice.igst_amount,
            cgst_amount=invoice.cgst_amount,
            sgst_amount=invoice.sgst_amount,
            cess_amount=invoice.cess_amount,
        )
    ]


def _validation_errors(*, invoice: Invoice, customer: Customer | None, dispatch: dict[str, Any], seller_gstin: str) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if not seller_gstin:
        errors.append({"code": "seller_gstin_missing"})
    if customer is None or not customer.gstin:
        errors.append({"code": "buyer_gstin_missing"})
    if invoice.date is None:
        errors.append({"code": "invoice_date_missing"})
    if not dispatch.get("from_pincode"):
        errors.append({"code": "from_pincode_missing"})
    if not dispatch.get("to_pincode"):
        errors.append({"code": "to_pincode_missing"})
    if dispatch.get("distance_km") in {None, ""}:
        errors.append({"code": "distance_km_missing"})
    if not dispatch.get("transport_mode"):
        errors.append({"code": "transport_mode_missing"})
    if str(dispatch.get("transport_mode", "")).strip().lower() == "road" and not dispatch.get("vehicle_number"):
        errors.append({"code": "vehicle_number_missing"})
    for index, item in enumerate(invoice.line_items, start=1):
        if not item.hsn_code:
            errors.append({"code": "line_item_hsn_missing", "line": index})
    return errors


def _payload(
    *,
    invoice: Invoice,
    customer: Customer | None,
    seller_gstin: str,
    dispatch: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema": "ares.eway_bill_draft.v1",
        "supply_type": "outward",
        "sub_supply_type": "supply",
        "document_type": "tax_invoice",
        "document_number": invoice.invoice_number,
        "document_date": invoice.date.isoformat() if invoice.date else None,
        "seller_gstin": seller_gstin,
        "buyer_gstin": customer.gstin if customer else None,
        "invoice_value": float(invoice.amount),
        "from_pincode": dispatch.get("from_pincode"),
        "to_pincode": dispatch.get("to_pincode"),
        "distance_km": dispatch.get("distance_km"),
        "transport_mode": dispatch.get("transport_mode"),
        "transporter_name": dispatch.get("transporter_name"),
        "vehicle_number": dispatch.get("vehicle_number"),
        "line_items": [
            {
                "description": item.description,
                "hsn_code": item.hsn_code,
                "quantity": item.quantity,
                "unit": item.unit,
                "taxable_value": float(item.taxable_value),
                "gst_rate_percent": item.gst_rate_percent,
            }
            for item in _line_items(invoice)
        ],
    }


def prepare_eway_bill_draft(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    invoice_id: str,
    seller_gstin: str,
    dispatch: dict[str, Any],
    requested_by: str,
) -> dict[str, Any]:
    """Prepare an approval-gated local e-way bill payload for a sales invoice."""
    invoice = _find_invoice(repository, invoice_id)
    customer = _find_customer(repository, invoice.customer_id)
    invoice_value = round(float(invoice.amount), 2)
    summary = {
        "eway_bill_required": invoice_value > EWAY_BILL_THRESHOLD,
        "validation_errors": 0,
        "invoice_value": invoice_value,
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": False,
        "external_submit_performed": False,
        "limitation": LOCAL_EWAY_BILL_LIMITATION,
    }
    if not summary["eway_bill_required"]:
        return {
            "mode": "local_contract_mock",
            "status": "not_required",
            "invoice_id": invoice_id,
            "summary": summary,
            "payload": {},
            "validation_errors": [],
            "audit": audit,
        }

    validation_errors = _validation_errors(invoice=invoice, customer=customer, dispatch=dispatch, seller_gstin=seller_gstin)
    summary["validation_errors"] = len(validation_errors)
    payload = _payload(invoice=invoice, customer=customer, seller_gstin=seller_gstin, dispatch=dispatch)
    audit["approval_required"] = True
    status = "needs_review" if validation_errors else "approval_required"
    batch_id = f"eway_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="prepare_eway_bill",
        proposed_action=f"Review local e-way bill draft for invoice {invoice.invoice_number}",
        data={
            "batch_id": batch_id,
            "invoice_id": invoice_id,
            "summary": summary,
            "payload": payload,
            "validation_errors": validation_errors,
            "mode": "local_contract_mock",
        },
        reason="E-way bill data affects regulated goods movement; owner/accountant review is required before use.",
        source="eway_bill",
        confidence=0.88,
        risk_level=RiskLevel.high,
        dedupe_key=f"eway_bill:{client_id}:{invoice_id}:{uuid4().hex[:8]}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": status,
        "approval_id": approval.id,
        "invoice_id": invoice_id,
        "summary": summary,
        "payload": payload,
        "validation_errors": validation_errors,
        "audit": audit,
    }
