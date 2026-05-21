from __future__ import annotations

from datetime import date

from apps.ares.ares.data.models import Invoice, Payment, PostDatedCheque, PurchaseInvoice, Supplier
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.cash_flow import build_daily_cash_flow_statement


def test_should_build_daily_cash_flow_statement_from_local_receipts_payables_and_pdc() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[
            Invoice(id="inv_due", invoice_number="INV-DUE", customer_id="Raj", amount=8000, due_date=date(2026, 5, 21), status="open"),
            Invoice(id="inv_overdue", invoice_number="INV-OLD", customer_id="Kumar", amount=2000, due_date=date(2026, 5, 20), status="overdue"),
            Invoice(id="inv_future", invoice_number="INV-FUT", customer_id="Maya", amount=9000, due_date=date(2026, 5, 25), status="open"),
        ],
        payments=[
            Payment(id="pay_today", customer_id="Raj", amount=5000, date=date(2026, 5, 21), mode="upi", reference="UTR1", status="reconciled"),
            Payment(id="pay_yesterday", customer_id="Kumar", amount=3000, date=date(2026, 5, 20), mode="cash", reference="CASH1", status="reconciled"),
            Payment(id="pay_unreconciled", customer_id="Unknown", amount=700, date=date(2026, 5, 21), mode="upi", reference="UTR2", status="unreconciled"),
        ],
        suppliers=[Supplier(id="sup_1", name="Soap Principal")],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_due",
                supplier_id="sup_1",
                invoice_number="PUR-DUE",
                due_date=date(2026, 5, 21),
                taxable_value=3000,
                tax_amount=540,
                status="booked",
            ),
            PurchaseInvoice(
                id="pinv_overdue",
                supplier_id="sup_1",
                invoice_number="PUR-OLD",
                due_date=date(2026, 5, 20),
                taxable_value=1000,
                tax_amount=180,
                status="overdue",
            ),
            PurchaseInvoice(
                id="pinv_paid",
                supplier_id="sup_1",
                invoice_number="PUR-PAID",
                due_date=date(2026, 5, 21),
                taxable_value=1000,
                tax_amount=180,
                status="paid",
            ),
        ],
    )
    repo.upsert_post_dated_cheque(
        PostDatedCheque(
            id="pdc_today",
            party_id="Raj",
            amount=4000,
            cheque_date=date(2026, 5, 21),
            bank_name="HDFC Bank",
            cheque_number="123456",
            status="scheduled",
        )
    )

    statement = build_daily_cash_flow_statement(repository=repo, as_of=date(2026, 5, 21), opening_cash=10000)

    assert statement["mode"] == "local_contract_mock"
    assert statement["summary"] == {
        "opening_cash": 10000.0,
        "actual_inflows": 5700.0,
        "expected_collections_due": 10000.0,
        "scheduled_pdc_inflows": 4000.0,
        "supplier_outflows_due": 4720.0,
        "net_cash_movement": 14980.0,
        "projected_closing_cash": 24980.0,
    }
    assert statement["actual_inflows"][0]["payment_id"] == "pay_today"
    assert statement["expected_collections"][0]["invoice_id"] == "inv_overdue"
    assert statement["supplier_outflows"][0]["purchase_invoice_id"] == "pinv_overdue"
    assert statement["risks"] == {
        "overdue_receivables": 1,
        "overdue_payables": 1,
        "unreconciled_inflows": 1,
    }
    assert statement["audit"] == {
        "external_bank_balance_called": False,
        "external_payment_gateway_called": False,
        "external_accounting_close_performed": False,
        "limitation": "Local daily cash-flow statement only; no bank, payment gateway, or accounting close integration was called.",
    }


def test_should_return_empty_cash_flow_sections_when_no_same_day_activity() -> None:
    repo = InMemoryRepository()

    statement = build_daily_cash_flow_statement(repository=repo, as_of=date(2026, 5, 21), opening_cash=2500)

    assert statement["summary"]["projected_closing_cash"] == 2500.0
    assert statement["actual_inflows"] == []
    assert statement["expected_collections"] == []
    assert statement["supplier_outflows"] == []
