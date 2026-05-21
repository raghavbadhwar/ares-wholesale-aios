from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, InvoiceLineItem, ProductSKU
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.return_damage import create_return_damage_case


def test_should_create_approval_gated_return_damage_case_with_estimated_credit_value() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Raj Retail")],
        products=[ProductSKU(id="sku_vim", name="Vim Bar", supplier_id="sup_1")],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_1",
                date=date(2026, 5, 10),
                amount=1180,
                taxable_value=1000,
                tax_amount=180,
                status="open",
                line_items=[
                    InvoiceLineItem(sku_id="sku_vim", description="Vim Bar", quantity=10, taxable_value=1000),
                ],
            )
        ],
    )
    approvals = ApprovalService(repo)

    result = create_return_damage_case(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        invoice_id="inv_1",
        reported_on=date(2026, 5, 21),
        requested_resolution="credit_note",
        items=[{"sku_id": "sku_vim", "quantity": 2, "reason": "damaged"}],
        requested_by="salesman",
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "approval_required"
    assert result["summary"] == {
        "items": 1,
        "quantity": 2.0,
        "estimated_credit_value": 200.0,
        "validation_errors": 0,
    }
    assert result["case"]["customer_id"] == "cust_1"
    assert result["case"]["invoice_id"] == "inv_1"
    assert result["case"]["items"] == [
        {"sku_id": "sku_vim", "quantity": 2.0, "reason": "damaged", "estimated_credit_value": 200.0}
    ]
    assert result["resolution_options"] == ["credit_note", "replacement", "supplier_claim"]
    assert result["audit"] == {
        "requested_by": "salesman",
        "approval_required": True,
        "external_logistics_pickup_called": False,
        "debit_note_posted": False,
        "supplier_portal_called": False,
        "limitation": "Local return/damage management only; no logistics pickup, debit-note posting, or supplier portal integration was called.",
    }
    assert repo.get_return_damage_cases()[0].status == "pending_review"
    assert repo.list_pending_approvals()[0].type == "review_return_damage_resolution"


def test_should_flag_return_quantity_above_original_invoice_quantity() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_1",
                date=date(2026, 5, 10),
                amount=100,
                taxable_value=100,
                tax_amount=0,
                line_items=[InvoiceLineItem(sku_id="sku_vim", description="Vim Bar", quantity=1, taxable_value=100)],
            )
        ],
    )

    result = create_return_damage_case(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        customer_id="cust_1",
        invoice_id="inv_1",
        reported_on=date(2026, 5, 21),
        requested_resolution="credit_note",
        items=[{"sku_id": "sku_vim", "quantity": 2, "reason": "damaged"}],
        requested_by="salesman",
    )

    assert result["status"] == "needs_review"
    assert result["validation_errors"] == [
        {"sku_id": "sku_vim", "code": "return_quantity_exceeds_invoice_quantity", "invoice_quantity": 1.0, "return_quantity": 2.0}
    ]
    assert repo.list_pending_approvals() == []
