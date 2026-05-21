"""Local logistics dispatch and delivery-status contracts."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, Customer, Invoice, LogisticsShipment, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_LOGISTICS_LIMITATION = (
    "Local logistics dispatch contract only; no carrier API, pickup booking, or live tracking integration was called."
)


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


def _find_shipment(repository: BusinessRepository, shipment_id: str) -> LogisticsShipment:
    for shipment in repository.get_logistics_shipments():
        if shipment.id == shipment_id:
            return shipment
    raise KeyError(f"Shipment not found: {shipment_id}")


def prepare_logistics_dispatch(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    invoice_id: str,
    carrier: str,
    packages: int,
    requested_by: str,
) -> dict[str, Any]:
    """Prepare a local shipment dispatch contract for approval."""
    invoice = _find_invoice(repository, invoice_id)
    customer = _find_customer(repository, invoice.customer_id)
    shipment = repository.upsert_logistics_shipment(
        LogisticsShipment(
            id=f"ship_{uuid4().hex[:12]}",
            invoice_id=invoice.id,
            customer_id=customer.id if customer else invoice.customer_id,
            carrier=carrier,
            packages=packages,
            status="pending_approval",
        )
    )
    shipment_payload = shipment.model_dump(mode="json")
    audit = {
        "requested_by": requested_by,
        "approval_required": True,
        "external_carrier_api_called": False,
        "dispatch_executed": False,
        "limitation": LOCAL_LOGISTICS_LIMITATION,
    }
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="prepare_logistics_dispatch",
        proposed_action=f"Review logistics dispatch for invoice {invoice.invoice_number}",
        data={
            "shipment": shipment_payload,
            "customer": customer.model_dump(mode="json") if customer else None,
            "mode": "local_contract_mock",
        },
        reason="Dispatch preparation affects customer delivery commitments and must be approved before execution.",
        source="logistics",
        confidence=0.86,
        risk_level=RiskLevel.medium,
        dedupe_key=f"logistics_dispatch:{client_id}:{shipment.id}",
    )
    return {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "shipment": shipment_payload,
        "audit": audit,
    }


def record_logistics_delivery_status(
    *,
    repository: BusinessRepository,
    client_id: str,
    shipment_id: str,
    delivery_status: str,
    provider_status_id: str,
    occurred_on: date,
) -> dict[str, Any]:
    """Record a local delivery-status receipt without calling a carrier API."""
    shipment = _find_shipment(repository, shipment_id)
    update = {
        "provider_status_id": provider_status_id,
        "delivery_status": delivery_status,
        "occurred_on": occurred_on.isoformat(),
        "external_carrier_api_called": False,
    }
    updated = shipment.model_copy(
        update={
            "delivery_status": delivery_status,
            "delivery_updates": [*shipment.delivery_updates, update],
        }
    )
    repository.upsert_logistics_shipment(updated)
    result = {
        "shipment_id": shipment_id,
        "delivery_status": delivery_status,
        "provider_status_id": provider_status_id,
        "external_carrier_api_called": False,
        "limitation": LOCAL_LOGISTICS_LIMITATION,
    }
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_{uuid4().hex[:12]}",
            client_id=client_id,
            approval_id=None,
            action_type="logistics_delivery_status",
            status="executed",
            result=result,
        )
    )
    return result
