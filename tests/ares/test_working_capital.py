from __future__ import annotations

from datetime import date

from apps.ares.ares.data.models import Invoice, PostDatedCheque, ProductSKU, PurchaseInvoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.working_capital import build_working_capital_intelligence


def test_should_build_working_capital_snapshot_from_local_operating_signals() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[
            Invoice(id="inv_open", invoice_number="INV-OPEN", customer_id="Raj", amount=20000, due_date=date(2026, 5, 30), status="open"),
            Invoice(id="inv_overdue", invoice_number="INV-OLD", customer_id="Kumar", amount=10000, due_date=date(2026, 5, 1), status="overdue"),
        ],
        products=[
            ProductSKU(id="sku_soap", name="Soap", buying_price=80, current_stock=100, reorder_level=20),
            ProductSKU(id="sku_low", name="Low Stock SKU", buying_price=70, current_stock=3, reorder_level=10),
        ],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_due",
                supplier_id="sup_1",
                invoice_number="PUR-DUE",
                due_date=date(2026, 5, 22),
                taxable_value=15000,
                tax_amount=2700,
                status="booked",
            )
        ],
    )
    repo.upsert_post_dated_cheque(
        PostDatedCheque(
            id="pdc_1",
            party_id="Raj",
            amount=5000,
            cheque_date=date(2026, 5, 25),
            bank_name="HDFC Bank",
            cheque_number="123456",
            status="scheduled",
        )
    )

    snapshot = build_working_capital_intelligence(repository=repo, as_of=date(2026, 5, 21), opening_cash=12000)

    assert snapshot["mode"] == "local_contract_mock"
    assert snapshot["summary"] == {
        "cash_on_hand": 12000.0,
        "receivables": 30000.0,
        "overdue_receivables": 10000.0,
        "payables": 17700.0,
        "inventory_value": 8210.0,
        "scheduled_pdc_inflows": 5000.0,
        "net_working_capital": 37510.0,
    }
    assert snapshot["risk_flags"] == [
        {"code": "overdue_receivable_pressure", "amount": 10000.0},
        {"code": "payable_pressure", "amount": 5700.0},
        {"code": "low_stock_replenishment_needed", "sku_count": 1},
    ]
    assert snapshot["audit"] == {
        "external_bank_balance_called": False,
        "account_aggregator_called": False,
        "financing_offer_generated": False,
        "limitation": "Local working-capital intelligence only; no bank, account-aggregator, or financing integration was called.",
    }


def test_should_return_clean_working_capital_snapshot_without_pressure() -> None:
    snapshot = build_working_capital_intelligence(repository=InMemoryRepository(), as_of=date(2026, 5, 21), opening_cash=5000)

    assert snapshot["summary"]["net_working_capital"] == 5000.0
    assert snapshot["risk_flags"] == []
