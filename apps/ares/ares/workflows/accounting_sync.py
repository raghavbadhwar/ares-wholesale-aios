"""Local accounting sync contract for Tally / Busy style ledgers."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, Customer, Invoice, Payment, RiskLevel, StockRecord
from apps.ares.ares.data.repository import BusinessRepository

SUPPORTED_ACCOUNTING_SYSTEMS = {"tally", "busy"}
LOCAL_SYNC_LIMITATION = "Local contract payload only; no live Tally/Busy connector was called."


def _normalize_system(system: str) -> str:
    normalized = system.strip().lower()
    if normalized not in SUPPORTED_ACCOUNTING_SYSTEMS:
        raise ValueError(f"Unsupported accounting sync system: {system}")
    return normalized


def _party_payload(customer: Customer) -> dict[str, Any]:
    return {
        "record_type": "party",
        "party_id": customer.id,
        "ledger_name": customer.name,
        "aliases": customer.aliases,
        "gstin": customer.gstin,
        "state_or_location": customer.location,
        "phone": customer.phone,
        "status": customer.status,
    }


def _invoice_payload(invoice: Invoice) -> dict[str, Any]:
    return {
        "record_type": "invoice",
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "voucher_type": "Sales",
        "party_ledger_id": invoice.customer_id,
        "invoice_date": invoice.date.isoformat() if invoice.date else None,
        "amount": float(invoice.amount),
        "tax_amount": float(invoice.tax_amount or 0),
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "status": invoice.status,
        "source_file": invoice.source_file,
    }


def _payment_payload(payment: Payment) -> dict[str, Any]:
    return {
        "record_type": "payment",
        "payment_id": payment.id,
        "party_ledger_id": payment.customer_id,
        "amount": float(payment.amount),
        "payment_date": payment.date.isoformat() if payment.date else None,
        "mode": payment.mode,
        "reference": payment.reference,
        "against_invoice_id": payment.matched_invoice_id,
        "candidate_invoice_ids": payment.candidate_invoice_ids,
        "unapplied_amount": float(payment.unapplied_amount),
        "status": payment.status,
        "audit_note": payment.audit_note,
    }


def _stock_item_payload(record: StockRecord) -> dict[str, Any]:
    return {
        "record_type": "stock_item",
        "sku_id": record.sku_id,
        "item_name": record.name,
        "current_stock": float(record.current_stock),
        "reorder_level": float(record.reorder_level),
        "unit": record.unit,
        "supplier_id": record.supplier_id,
        "last_updated": record.last_updated.isoformat(),
    }


def prepare_accounting_sync_export(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    system: str,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare an approval-gated local payload shaped for Tally/Busy ledgers.

    This is intentionally a contract/mock surface. It performs no external write.
    """
    normalized_system = _normalize_system(system)
    batch_id = f"sync_{uuid4().hex[:12]}"
    parties = [_party_payload(customer) for customer in repository.get_customers()]
    invoices = [_invoice_payload(invoice) for invoice in repository.get_invoices()]
    payments = [_payment_payload(payment) for payment in repository.get_payments()]
    stock_items = [_stock_item_payload(record) for record in repository.get_stock_records()]
    summary = {"parties": len(parties), "invoices": len(invoices), "payments": len(payments), "stock_items": len(stock_items)}
    payload = {
        "schema": "ares.accounting_sync.v1",
        "system_style": normalized_system,
        "parties": parties,
        "invoices": invoices,
        "payments": payments,
        "stock_items": stock_items,
        "reconciliation_status": {
            "invoice_ids": [invoice["invoice_id"] for invoice in invoices],
            "payment_ids": [payment["payment_id"] for payment in payments],
            "stock_item_ids": [item["sku_id"] for item in stock_items],
            "open_invoice_ids": [invoice["invoice_id"] for invoice in invoices if invoice["status"] in {"open", "overdue"}],
            "unreconciled_payment_ids": [
                payment["payment_id"] for payment in payments if payment["status"] in {"pending", "unreconciled", "needs_review"}
            ],
        },
    }
    audit = {
        "requested_by": requested_by,
        "approval_required": True,
        "external_write_performed": False,
        "limitation": LOCAL_SYNC_LIMITATION,
    }

    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="export_accounting_sync",
        proposed_action=f"Approve local {normalized_system.title()} accounting sync export",
        data={"batch_id": batch_id, "system": normalized_system, "summary": summary, "mode": "local_contract_mock"},
        reason="Accounting ledger exports can change books after import; owner/accountant approval is required first.",
        source="accounting_sync",
        confidence=0.9,
        risk_level=RiskLevel.high,
        dedupe_key=f"accounting_sync_export:{normalized_system}:{batch_id}",
    )

    return {
        "batch_id": batch_id,
        "mode": "local_contract_mock",
        "system": normalized_system,
        "status": "approval_required",
        "approval_id": approval.id,
        "summary": summary,
        "payload": payload,
        "audit": audit,
    }


def import_accounting_sync_status(
    *,
    repository: BusinessRepository,
    client_id: str,
    system: str,
    status_payload: dict[str, Any],
) -> dict[str, Any]:
    """Import an accounting-system status receipt as audit metadata only."""
    normalized_system = _normalize_system(system)
    result = {
        "batch_id": status_payload.get("batch_id"),
        "mode": "local_contract_mock",
        "system": normalized_system,
        "status": status_payload.get("status", "unknown"),
        "external_reference": status_payload.get("external_reference"),
        "items": list(status_payload.get("items", [])),
        "audit": {
            "external_write_performed": False,
            "ledger_mutation_performed": False,
            "limitation": LOCAL_SYNC_LIMITATION,
        },
    }
    repository.save_action_log(
        ActionExecutionLog(
            id=f"log_{uuid4().hex[:12]}",
            client_id=client_id,
            action_type="import_accounting_sync_status",
            status=result["status"],
            result=result,
        )
    )
    return result
