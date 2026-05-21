"""Local return and damage management."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Invoice, InvoiceLineItem, ReturnDamageCase, ReturnDamageCaseItem, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_RETURN_DAMAGE_LIMITATION = (
    "Local return/damage management only; no logistics pickup, debit-note posting, or supplier portal integration was called."
)
RESOLUTION_OPTIONS = ["credit_note", "replacement", "supplier_claim"]


def _find_invoice(repository: BusinessRepository, invoice_id: str) -> Invoice | None:
    for invoice in repository.get_invoices():
        if invoice.id == invoice_id:
            return invoice
    return None


def _invoice_line_by_sku(invoice: Invoice) -> dict[str, InvoiceLineItem]:
    return {
        line.sku_id: line
        for line in invoice.line_items
        if line.sku_id
    }


def _line_unit_value(line: InvoiceLineItem) -> float:
    if not line.quantity:
        return 0.0
    return round(float(line.taxable_value) / float(line.quantity), 2)


def _validate_and_build_items(invoice: Invoice | None, items: list[dict[str, Any]]) -> tuple[list[ReturnDamageCaseItem], list[dict[str, Any]]]:
    validation_errors: list[dict[str, Any]] = []
    built_items: list[ReturnDamageCaseItem] = []
    lines = _invoice_line_by_sku(invoice) if invoice else {}
    if invoice is None:
        validation_errors.append({"code": "invoice_missing"})
        return built_items, validation_errors

    for item in items:
        sku_id = item.get("sku_id")
        quantity = float(item.get("quantity", 0))
        reason = str(item.get("reason") or "return")
        line = lines.get(sku_id)
        if line is None:
            validation_errors.append({"sku_id": sku_id, "code": "invoice_line_missing"})
            continue
        invoice_quantity = float(line.quantity or 0)
        if quantity > invoice_quantity:
            validation_errors.append(
                {
                    "sku_id": sku_id,
                    "code": "return_quantity_exceeds_invoice_quantity",
                    "invoice_quantity": invoice_quantity,
                    "return_quantity": quantity,
                }
            )
            continue
        built_items.append(
            ReturnDamageCaseItem(
                sku_id=sku_id,
                quantity=quantity,
                reason=reason,
                estimated_credit_value=round(quantity * _line_unit_value(line), 2),
            )
        )
    return built_items, validation_errors


def create_return_damage_case(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    customer_id: str,
    invoice_id: str,
    reported_on: date,
    requested_resolution: str,
    items: list[dict[str, Any]],
    requested_by: str,
) -> dict[str, Any]:
    """Create a local return/damage case and approval-gated resolution plan."""
    invoice = _find_invoice(repository, invoice_id)
    built_items, validation_errors = _validate_and_build_items(invoice, items)
    summary = {
        "items": len(built_items),
        "quantity": round(sum(item.quantity for item in built_items), 2),
        "estimated_credit_value": round(sum(item.estimated_credit_value for item in built_items), 2),
        "validation_errors": len(validation_errors),
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": not validation_errors and bool(built_items),
        "external_logistics_pickup_called": False,
        "debit_note_posted": False,
        "supplier_portal_called": False,
        "limitation": LOCAL_RETURN_DAMAGE_LIMITATION,
    }
    if validation_errors or not built_items:
        return {
            "mode": "local_contract_mock",
            "status": "needs_review",
            "summary": summary,
            "case": None,
            "resolution_options": RESOLUTION_OPTIONS,
            "validation_errors": validation_errors,
            "audit": audit,
        }

    case = repository.upsert_return_damage_case(
        ReturnDamageCase(
            id=f"ret_{uuid4().hex[:12]}",
            customer_id=customer_id,
            invoice_id=invoice_id,
            reported_on=reported_on,
            requested_resolution=requested_resolution,
            items=built_items,
            status="pending_review",
        )
    )
    case_payload = case.model_dump(mode="json")
    batch_id = f"return_damage_{uuid4().hex[:12]}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_return_damage_resolution",
        proposed_action=f"Review return/damage resolution for invoice {invoice.invoice_number if invoice else invoice_id}",
        data={
            "batch_id": batch_id,
            "case": case_payload,
            "summary": summary,
            "resolution_options": RESOLUTION_OPTIONS,
            "mode": "local_contract_mock",
        },
        reason="Return/damage resolution can affect stock, customer credit, supplier claims, and ledgers; owner review is required first.",
        source="return_damage",
        confidence=0.86,
        risk_level=RiskLevel.medium,
        dedupe_key=f"return_damage:{client_id}:{case.id}:{batch_id}",
    )
    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "summary": summary,
        "case": case_payload,
        "resolution_options": RESOLUTION_OPTIONS,
        "validation_errors": [],
        "audit": audit,
    }
