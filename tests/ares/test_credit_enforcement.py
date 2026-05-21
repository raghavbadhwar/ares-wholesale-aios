from __future__ import annotations

from datetime import date, timedelta

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.message_ingest import ingest_forwarded_message
from apps.ares.ares.data.models import Customer, Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.order_capture import capture_order


def test_capture_order_creates_credit_extension_approval_when_exposure_exceeds_limit() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="Raj Traders", name="Raj Traders", credit_limit=10000)],
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj Traders", amount=8500, status="open")],
    )
    approvals = ApprovalService(repo)
    event = ingest_forwarded_message(
        client_id="demo",
        sender="Raj Traders",
        message_text="Raj Traders 3 carton Surf Excel bhejna",
    )

    capture_order(event, repo, approvals)

    pending = repo.list_pending_approvals()
    assert len(pending) == 1
    assert pending[0].type == "approve_credit_extension"
    assert pending[0].data["customer"] == "Raj Traders"
    assert pending[0].data["credit_limit"] == 10000
    assert pending[0].data["projected_exposure"] > pending[0].data["credit_limit"]


def test_capture_order_creates_block_dispatch_when_customer_is_past_hard_stop_overdue_days() -> None:
    overdue_date = date.today() - timedelta(days=61)
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="Raj Traders", name="Raj Traders", credit_limit=10000)],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="Raj Traders",
                amount=4000,
                status="overdue",
                due_date=overdue_date,
            )
        ],
    )
    approvals = ApprovalService(repo)
    event = ingest_forwarded_message(
        client_id="demo",
        sender="Raj Traders",
        message_text="Raj Traders 2 carton Tide bhejna",
    )

    capture_order(event, repo, approvals)

    pending = repo.list_pending_approvals()
    assert len(pending) == 1
    assert pending[0].type == "block_dispatch"
    assert pending[0].data["customer"] == "Raj Traders"
    assert pending[0].data["oldest_overdue_days"] >= 61


def test_capture_order_keeps_clean_order_unblocked_when_customer_within_limit() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="Raj Traders", name="Raj Traders", credit_limit=10000)],
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj Traders", amount=2000, status="open")],
    )
    approvals = ApprovalService(repo)
    event = ingest_forwarded_message(
        client_id="demo",
        sender="Raj Traders",
        message_text="Raj Traders 1 carton Surf Excel bhejna",
    )

    order = capture_order(event, repo, approvals)

    assert order.customer_id == "Raj Traders"
    assert repo.list_pending_approvals() == []
