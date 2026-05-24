from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import PurchaseInvoice, SupplierPayment, SupplierPaymentAllocation, TaxEvent
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.supplier_payments import ingest_supplier_payment_receipt


def test_should_mark_purchase_invoice_paid_when_supplier_payment_exactly_matches_one_open_invoice() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=10000,
                tax_amount=2500,
                status="overdue",
            ),
            PurchaseInvoice(
                id="pinv_2",
                supplier_id="sup_soap",
                invoice_number="PINV-2",
                taxable_value=4000,
                tax_amount=1000,
                status="booked",
            ),
        ]
    )

    result = ingest_supplier_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt={
            "supplier_id": "sup_soap",
            "amount": 12500,
            "paid_on": date(2026, 5, 23),
            "mode": "bank_transfer",
            "reference": "SUP-UTR-1",
        },
    )

    assert result["status"] == "reconciled"
    assert result["matched_purchase_invoice_id"] == "pinv_1"
    assert result["allocated_amount"] == 12500.0
    assert result["allocations"][0]["purchase_invoice_id"] == "pinv_1"
    assert repo.get_supplier_payments()[0].matched_purchase_invoice_id == "pinv_1"
    assert repo.get_supplier_payments()[0].status == "reconciled"
    assert repo.effective_purchase_invoice_projection(repo.get_purchase_invoices()[0])["status"] == "paid"
    assert repo.get_supplier_payment_allocations()[0].amount == 12500.0
    assert repo.get_ledger_entries()[0].entry_type == "supplier_payment_allocation"
    assert repo.get_ledger_entries()[0].debit_account == "Accounts Payable"
    assert repo.list_pending_approvals() == []


def test_should_require_approval_when_supplier_payment_matches_multiple_open_invoices() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=10000,
                tax_amount=2500,
                status="overdue",
            ),
            PurchaseInvoice(
                id="pinv_2",
                supplier_id="sup_soap",
                invoice_number="PINV-2",
                taxable_value=10000,
                tax_amount=2500,
                status="booked",
            ),
        ]
    )

    result = ingest_supplier_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt={"supplier_id": "sup_soap", "amount": 12500, "reference": "SUP-UTR-MULTI"},
    )

    assert result["status"] == "needs_review"
    assert result["candidate_purchase_invoice_ids"] == ["pinv_1", "pinv_2"]
    assert repo.get_supplier_payments()[0].status == "needs_review"
    assert repo.list_pending_approvals()[0].type == "review_supplier_payment_reconciliation"


def test_should_record_supplier_advance_when_payment_exceeds_single_invoice() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=7200,
                tax_amount=1800,
                status="booked",
            )
        ]
    )

    result = ingest_supplier_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt={"supplier_id": "sup_soap", "amount": 10000, "reference": "SUP-UTR-EXCESS"},
    )

    assert result["status"] == "partially_reconciled"
    assert result["matched_purchase_invoice_id"] == "pinv_1"
    assert result["allocated_amount"] == 9000.0
    assert result["unapplied_amount"] == 1000.0
    assert repo.get_supplier_payments()[0].unapplied_amount == 1000.0
    assert repo.effective_purchase_invoice_projection(repo.get_purchase_invoices()[0])["status"] == "paid"
    assert {entry.entry_type for entry in repo.get_ledger_entries()} == {
        "supplier_payment_allocation",
        "supplier_advance",
    }


def test_should_ignore_duplicate_supplier_payment_when_provider_event_id_replays() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=7200,
                tax_amount=1800,
                status="booked",
            )
        ]
    )
    receipt = {
        "supplier_id": "sup_soap",
        "amount": 9000,
        "reference": "SUP-UTR-DUPLICATE",
        "provider": "bank_api",
        "external_event_id": "sup_evt_1",
        "source_event_type": "supplier_payment.settled",
        "signature_verification_status": "verified",
    }

    first = ingest_supplier_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt=receipt,
    )
    duplicate = ingest_supplier_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt=receipt,
    )

    assert first["status"] == "reconciled"
    assert duplicate["supplier_payment_id"] == first["supplier_payment_id"]
    assert duplicate["external_event_id"] == "sup_evt_1"
    assert repo.get_supplier_payments()[0].provider == "bank_api"
    assert repo.get_supplier_payments()[0].signature_verification_status == "verified"
    assert len(repo.get_supplier_payments()) == 1


def test_should_block_unverified_external_supplier_payment_without_mutating_purchase_invoice() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=7200,
                tax_amount=1800,
                status="booked",
            )
        ]
    )

    result = ingest_supplier_payment_receipt(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        receipt={
            "supplier_id": "sup_soap",
            "amount": 9000,
            "provider": "bank_api",
            "external_event_id": "sup_evt_blocked",
            "source_event_type": "supplier_payment.settled",
        },
    )

    assert result["status"] == "blocked_unverified_signature"
    assert result["matched_purchase_invoice_id"] is None
    assert result["candidate_purchase_invoice_ids"] == ["pinv_1"]
    assert repo.get_supplier_payments()[0].status == "blocked_unverified_signature"
    assert repo.effective_purchase_invoice_projection(repo.get_purchase_invoices()[0])["status"] == "booked"
    assert repo.get_supplier_payment_allocations() == []


def test_should_refresh_purchase_contract_metadata_when_allocation_changes_after_invoice_booking() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_refresh",
                supplier_id="sup_soap",
                invoice_number="PINV-REFRESH",
                date=date(2026, 5, 21),
                taxable_value=1000,
                tax_amount=180,
                status="open",
            )
        ]
    )

    initial_tax_event = {event.id: event for event in repo.get_tax_events()}["tax_purchase_pinv_refresh"]
    assert initial_tax_event.metadata["invoice_status"] == "booked"
    assert initial_tax_event.metadata["raw_invoice_status"] == "open"

    repo.upsert_supplier_payment_allocation(
        SupplierPaymentAllocation(
            id="sup_alloc_refresh",
            supplier_payment_id="sup_pay_refresh",
            purchase_invoice_id="pinv_refresh",
            amount=1180,
            status="posted",
        )
    )

    refreshed_tax_event = {event.id: event for event in repo.get_tax_events()}["tax_purchase_pinv_refresh"]
    refreshed_ledger_entry = {
        entry.id: entry for entry in repo.get_ledger_entries()
    }["led_purchase_pinv_refresh_base"]
    assert refreshed_tax_event.metadata["invoice_status"] == "paid"
    assert refreshed_tax_event.metadata["raw_invoice_status"] == "open"
    assert refreshed_ledger_entry.metadata["invoice_status"] == "paid"
    assert refreshed_ledger_entry.metadata["raw_invoice_status"] == "open"


def test_should_refresh_purchase_ledger_from_direct_base_tax_event_write() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_tax_refresh",
                supplier_id="sup_soap",
                invoice_number="PINV-TAX-REFRESH",
                date=date(2026, 5, 21),
                taxable_value=1000,
                tax_amount=180,
                status="open",
            )
        ]
    )

    repo.upsert_tax_event(
        TaxEvent(
            id="tax_purchase_pinv_tax_refresh",
            event_type="purchase_input_tax",
            source_type="purchase_invoice",
            source_id="pinv_tax_refresh",
            document_type="purchase_invoice",
            document_id="pinv_tax_refresh",
            document_number="PINV-TAX-REFRESH",
            event_date=date(2026, 5, 21),
            taxable_value=1500,
            tax_amount=270,
            status="posted",
        )
    )

    refreshed_tax_event = {
        event.id: event for event in repo.get_tax_events()
    }["tax_purchase_pinv_tax_refresh"]
    refreshed_ledger_entry = {
        entry.id: entry for entry in repo.get_ledger_entries()
    }["led_purchase_pinv_tax_refresh_base"]
    assert refreshed_tax_event.metadata["invoice_status"] == "booked"
    assert refreshed_tax_event.metadata["raw_invoice_status"] == "open"
    assert refreshed_ledger_entry.amount == 1500.0
    assert refreshed_ledger_entry.metadata["invoice_status"] == "booked"
    assert refreshed_ledger_entry.metadata["raw_invoice_status"] == "open"


def test_should_compute_purchase_metadata_status_from_stream_backed_amounts() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_tax_status",
                supplier_id="sup_soap",
                invoice_number="PINV-TAX-STATUS",
                date=date(2026, 5, 21),
                taxable_value=1000,
                tax_amount=180,
                status="open",
            )
        ],
        supplier_payments=[
            SupplierPayment(
                id="sup_pay_tax_status",
                supplier_id="sup_soap",
                amount=1180,
                date=date(2026, 5, 21),
                status="partially_reconciled",
            )
        ],
        supplier_payment_allocations=[
            SupplierPaymentAllocation(
                id="sup_alloc_tax_status",
                supplier_payment_id="sup_pay_tax_status",
                purchase_invoice_id="pinv_tax_status",
                amount=1180,
                status="posted",
            )
        ],
    )

    repo.upsert_tax_event(
        TaxEvent(
            id="tax_purchase_pinv_tax_status",
            event_type="purchase_input_tax",
            source_type="purchase_invoice",
            source_id="pinv_tax_status",
            document_type="purchase_invoice",
            document_id="pinv_tax_status",
            document_number="PINV-TAX-STATUS",
            event_date=date(2026, 5, 21),
            taxable_value=1500,
            tax_amount=270,
            status="posted",
        )
    )

    refreshed_tax_event = {
        event.id: event for event in repo.get_tax_events()
    }["tax_purchase_pinv_tax_status"]
    refreshed_ledger_entry = {
        entry.id: entry for entry in repo.get_ledger_entries()
    }["led_purchase_pinv_tax_status_base"]
    assert repo.effective_purchase_invoice_projection(repo.get_purchase_invoices()[0])["status"] == "partially_paid"
    assert refreshed_tax_event.metadata["invoice_status"] == "partially_paid"
    assert refreshed_ledger_entry.metadata["invoice_status"] == "partially_paid"
