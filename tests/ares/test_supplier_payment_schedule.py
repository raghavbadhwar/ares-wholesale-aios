from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import PurchaseInvoice, Supplier
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.supplier_payments import prepare_supplier_payment_schedule


def test_should_prepare_approval_gated_supplier_payment_schedule() -> None:
    repo = InMemoryRepository.from_records(
        suppliers=[
            Supplier(id="sup_soap", name="Soap Principal", gstin="27PRINC1234F1Z5"),
            Supplier(id="sup_food", name="Food Principal", gstin="27FOODX1234F1Z5"),
        ],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_overdue",
                supplier_id="sup_soap",
                supplier_gstin="27PRINC1234F1Z5",
                invoice_number="PUR-OVERDUE",
                date=date(2026, 5, 1),
                due_date=date(2026, 5, 10),
                taxable_value=10000,
                tax_amount=1800,
                status="booked",
            ),
            PurchaseInvoice(
                id="pinv_discount",
                supplier_id="sup_food",
                supplier_gstin="27FOODX1234F1Z5",
                invoice_number="PUR-DISCOUNT",
                date=date(2026, 5, 12),
                due_date=date(2026, 5, 25),
                taxable_value=20000,
                tax_amount=3600,
                early_payment_discount_amount=500,
                early_payment_discount_deadline=date(2026, 5, 21),
                status="booked",
            ),
        ],
    )
    approvals = ApprovalService(repo)

    schedule = prepare_supplier_payment_schedule(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        as_of=date(2026, 5, 20),
        cash_available=30000,
        requested_by="owner",
    )

    assert approvals.requires_approval("schedule_supplier_payments") is True
    assert schedule["mode"] == "local_contract_mock"
    assert schedule["status"] == "approval_required"
    assert schedule["summary"] == {
        "payable_count": 2,
        "overdue_count": 1,
        "due_next_7_days": 1,
        "early_payment_discount_opportunities": 1,
        "total_payable": 35400.0,
        "recommended_payment_amount": 30000.0,
    }
    assert schedule["recommended_payments"][0]["purchase_invoice_id"] == "pinv_overdue"
    assert schedule["recommended_payments"][0]["priority"] == "overdue"
    assert schedule["recommended_payments"][1]["purchase_invoice_id"] == "pinv_discount"
    assert schedule["recommended_payments"][1]["discount_amount"] == 500.0
    assert schedule["audit"]["external_payment_performed"] is False
    assert schedule["audit"]["limitation"] == "Local supplier payment schedule only; no banking or UPI payment was executed."

    approval = repo.list_pending_approvals()[0]
    assert approval.type == "schedule_supplier_payments"
    assert approval.data["summary"] == schedule["summary"]


def test_should_skip_paid_supplier_invoices_and_return_noop_when_no_open_payables() -> None:
    repo = InMemoryRepository.from_records(
        suppliers=[Supplier(id="sup_soap", name="Soap Principal", gstin="27PRINC1234F1Z5")],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_paid",
                supplier_id="sup_soap",
                supplier_gstin="27PRINC1234F1Z5",
                invoice_number="PUR-PAID",
                date=date(2026, 5, 1),
                due_date=date(2026, 5, 10),
                taxable_value=10000,
                tax_amount=1800,
                status="paid",
            )
        ],
    )

    schedule = prepare_supplier_payment_schedule(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        as_of=date(2026, 5, 20),
        cash_available=100000,
        requested_by="owner",
    )

    assert schedule["status"] == "no_open_payables"
    assert schedule["summary"]["payable_count"] == 0
    assert schedule["recommended_payments"] == []
    assert repo.list_pending_approvals() == []
