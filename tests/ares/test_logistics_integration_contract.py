from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.logistics import prepare_logistics_dispatch, record_logistics_delivery_status


def test_should_prepare_approval_gated_logistics_dispatch_contract() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Raj Retail", phone="+919999999999", location="Mumbai")],
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=5000, status="open")],
    )
    approvals = ApprovalService(repo)

    dispatch = prepare_logistics_dispatch(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        invoice_id="inv_1",
        carrier="local_courier",
        packages=2,
        requested_by="dispatcher",
    )

    assert dispatch["mode"] == "local_contract_mock"
    assert dispatch["status"] == "approval_required"
    assert dispatch["shipment"]["invoice_id"] == "inv_1"
    assert dispatch["shipment"]["customer_id"] == "cust_1"
    assert dispatch["shipment"]["carrier"] == "local_courier"
    assert dispatch["shipment"]["packages"] == 2
    assert dispatch["audit"] == {
        "requested_by": "dispatcher",
        "approval_required": True,
        "external_carrier_api_called": False,
        "dispatch_executed": False,
        "limitation": "Local logistics dispatch contract only; no carrier API, pickup booking, or live tracking integration was called.",
    }
    assert repo.get_logistics_shipments()[0].status == "pending_approval"
    assert repo.list_pending_approvals()[0].type == "prepare_logistics_dispatch"


def test_should_record_local_delivery_status_without_calling_carrier_api() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Raj Retail", phone="+919999999999", location="Mumbai")],
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=5000, status="open")],
    )
    dispatch = prepare_logistics_dispatch(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        invoice_id="inv_1",
        carrier="local_courier",
        packages=2,
        requested_by="dispatcher",
    )

    receipt = record_logistics_delivery_status(
        repository=repo,
        client_id="demo",
        shipment_id=dispatch["shipment"]["id"],
        delivery_status="delivered",
        provider_status_id="mock_status_1",
        occurred_on=date(2026, 5, 21),
    )

    assert receipt["delivery_status"] == "delivered"
    assert receipt["external_carrier_api_called"] is False
    assert repo.get_logistics_shipments()[0].delivery_status == "delivered"
    assert repo.list_action_logs()[-1].action_type == "logistics_delivery_status"
