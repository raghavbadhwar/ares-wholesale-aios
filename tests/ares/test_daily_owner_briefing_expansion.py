from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, ProductSKU, PurchaseInvoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.daily_brief import run_daily_brief


def test_daily_owner_brief_should_include_collections_and_working_capital_signals() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_risk", name="Risk Retail", credit_limit=1000)],
        invoices=[
            Invoice(id="inv_old", invoice_number="INV-OLD", customer_id="cust_risk", amount=5000, due_date=date(2026, 5, 1), status="overdue")
        ],
        products=[ProductSKU(id="sku_soap", name="Soap", buying_price=50, current_stock=10, reorder_level=20)],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_1",
                invoice_number="PUR-1",
                due_date=date(2026, 5, 21),
                taxable_value=2000,
                tax_amount=360,
                status="booked",
            )
        ],
    )

    brief = run_daily_brief(
        repo,
        ApprovalService(repo),
        client_id="demo",
        language="english_hinglish",
        today=date(2026, 5, 21),
        opening_cash=1000,
    )

    assert brief["collections"]["summary"]["overdue_outstanding"] == 5000.0
    assert brief["collections"]["summary"]["high_risk_parties"] == 1
    assert brief["working_capital"]["summary"] == {
        "cash_on_hand": 1000.0,
        "receivables": 5000.0,
        "overdue_receivables": 5000.0,
        "payables": 2360.0,
        "inventory_value": 500.0,
        "scheduled_pdc_inflows": 0,
        "net_working_capital": 4140.0,
    }
    assert any("Collect INR 5000 from Risk Retail" in action for action in brief["top_actions"])
    assert brief["audit"] == {
        "scheduled_delivery_performed": False,
        "whatsapp_automation_performed": False,
        "limitation": "Local daily owner briefing only; no production scheduler or WhatsApp delivery automation was called.",
    }
