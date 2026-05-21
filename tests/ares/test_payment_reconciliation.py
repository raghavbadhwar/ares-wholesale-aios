from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.payment_reconciliation import ingest_payment_receipt


def test_should_mark_invoice_paid_when_receipt_exactly_matches_one_open_invoice() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[
            Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj Traders", amount=12500, status="overdue"),
            Invoice(id="inv_2", invoice_number="INV-2", customer_id="Raj Traders", amount=5000, status="open"),
        ]
    )

    result = ingest_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt={
            "party_id": "Raj Traders",
            "amount": 12500,
            "received_on": date(2026, 5, 21),
            "mode": "upi",
            "reference": "UTR123456789",
        },
    )

    assert result["status"] == "reconciled"
    assert result["matched_invoice_id"] == "inv_1"
    assert repo.get_payments()[0].matched_invoice_id == "inv_1"
    assert repo.get_payments()[0].status == "reconciled"
    assert repo.get_invoices()[0].status == "paid"
    assert repo.list_pending_approvals() == []


def test_should_require_approval_when_receipt_matches_multiple_open_invoices() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[
            Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj Traders", amount=10000, status="overdue"),
            Invoice(id="inv_2", invoice_number="INV-2", customer_id="Raj Traders", amount=10000, status="open"),
        ]
    )

    result = ingest_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt={"party_id": "Raj Traders", "amount": 10000, "reference": "UTR-MULTI"},
    )

    assert result["status"] == "needs_review"
    assert result["candidate_invoice_ids"] == ["inv_1", "inv_2"]
    assert repo.get_payments()[0].status == "needs_review"
    assert repo.get_invoices()[0].status == "overdue"
    assert repo.list_pending_approvals()[0].type == "review_payment_reconciliation"


def test_should_record_unapplied_balance_when_receipt_exceeds_single_invoice() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj Traders", amount=9000, status="open")]
    )

    result = ingest_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt={"party_id": "Raj Traders", "amount": 10000, "reference": "UTR-EXCESS"},
    )

    assert result["status"] == "partially_reconciled"
    assert result["matched_invoice_id"] == "inv_1"
    assert result["unapplied_amount"] == 1000.0
    assert repo.get_payments()[0].unapplied_amount == 1000.0
    assert repo.get_invoices()[0].status == "paid"


def test_should_keep_unknown_party_receipt_unreconciled_and_auditable() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj Traders", amount=9000, status="open")]
    )

    result = ingest_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt={"party_id": "Unknown Store", "amount": 9000, "reference": "UTR-UNKNOWN"},
    )

    assert result["status"] == "unreconciled"
    assert result["candidate_invoice_ids"] == []
    assert repo.get_payments()[0].status == "unreconciled"
    assert repo.get_payments()[0].audit_note == "No open invoice matched party_id and amount."
    assert repo.get_invoices()[0].status == "open"
