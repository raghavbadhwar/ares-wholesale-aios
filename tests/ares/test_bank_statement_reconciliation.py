from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Payment, PurchaseInvoice, Supplier
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.bank_reconciliation import reconcile_bank_statement


def test_should_match_bank_statement_credits_and_debits_to_local_records() -> None:
    repo = InMemoryRepository.from_records(
        payments=[
            Payment(
                id="pay_1",
                customer_id="cust_1",
                amount=12500,
                date=date(2026, 5, 21),
                mode="upi",
                reference="UTR123",
                status="reconciled",
            )
        ],
        suppliers=[Supplier(id="sup_1", name="Soap Principal")],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_1",
                invoice_number="PUR-100",
                date=date(2026, 5, 15),
                due_date=date(2026, 5, 21),
                taxable_value=15000,
                tax_amount=2700,
                status="booked",
            )
        ],
    )

    result = reconcile_bank_statement(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        statement_entries=[
            {
                "entry_id": "stmt_credit",
                "posted_on": date(2026, 5, 21),
                "direction": "credit",
                "amount": 12500,
                "reference": "UTR123",
                "narration": "UPI/UTR123/Raj Traders",
            },
            {
                "entry_id": "stmt_debit",
                "posted_on": date(2026, 5, 21),
                "direction": "debit",
                "amount": 17700,
                "reference": "NEFT555",
                "narration": "NEFT Soap Principal PUR-100",
            },
        ],
        requested_by="owner",
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "matched"
    assert result["summary"] == {
        "entries": 2,
        "credit_total": 12500.0,
        "debit_total": 17700.0,
        "matched_customer_receipts": 1,
        "matched_supplier_payments": 1,
        "ambiguous_entries": 0,
        "unmatched_entries": 0,
    }
    assert result["matched_entries"] == [
        {
            "bank_entry_id": "stmt_credit",
            "direction": "credit",
            "amount": 12500.0,
            "matched_record_type": "payment",
            "matched_record_id": "pay_1",
            "code": "reference_match",
        },
        {
            "bank_entry_id": "stmt_debit",
            "direction": "debit",
            "amount": 17700.0,
            "matched_record_type": "purchase_invoice",
            "matched_record_id": "pinv_1",
            "code": "supplier_amount_narration_match",
        },
    ]
    assert result["review_entries"] == []
    assert result["audit"] == {
        "requested_by": "owner",
        "external_bank_feed_called": False,
        "account_aggregator_called": False,
        "ledger_posting_performed": False,
        "limitation": "Local bank-statement reconciliation only; no live bank feed, account aggregator, or banking API was called.",
    }
    assert repo.list_pending_approvals() == []


def test_should_create_review_approval_for_unmatched_bank_statement_entries() -> None:
    repo = InMemoryRepository.from_records(
        payments=[
            Payment(id="pay_a", customer_id="cust_a", amount=5000, date=date(2026, 5, 21), reference="A", status="reconciled"),
            Payment(id="pay_b", customer_id="cust_b", amount=5000, date=date(2026, 5, 21), reference="B", status="reconciled"),
        ]
    )
    approvals = ApprovalService(repo)

    result = reconcile_bank_statement(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        statement_entries=[
            {
                "entry_id": "stmt_ambiguous",
                "posted_on": date(2026, 5, 21),
                "direction": "credit",
                "amount": 5000,
                "reference": "",
                "narration": "Cash deposit",
            },
            {
                "entry_id": "stmt_unmatched",
                "posted_on": date(2026, 5, 21),
                "direction": "debit",
                "amount": 999,
                "reference": "BANKCHG",
                "narration": "Bank charges",
            },
        ],
        requested_by="owner",
    )

    assert result["status"] == "needs_review"
    assert result["summary"]["ambiguous_entries"] == 1
    assert result["summary"]["unmatched_entries"] == 1
    assert result["review_entries"] == [
        {
            "bank_entry_id": "stmt_ambiguous",
            "direction": "credit",
            "amount": 5000.0,
            "candidate_record_type": "payment",
            "candidate_record_ids": ["pay_a", "pay_b"],
            "code": "ambiguous_amount_match",
        },
        {
            "bank_entry_id": "stmt_unmatched",
            "direction": "debit",
            "amount": 999.0,
            "candidate_record_type": None,
            "candidate_record_ids": [],
            "code": "unmatched_bank_entry",
        },
    ]
    assert result["approval_id"] == repo.list_pending_approvals()[0].id
    assert repo.list_pending_approvals()[0].type == "review_bank_statement_reconciliation"
