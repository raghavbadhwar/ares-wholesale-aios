from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, PurchaseInvoice, Supplier
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.tds_tcs import prepare_tds_tcs_computation


def test_should_compute_local_tcs_on_sales_threshold_crossing_and_tds_on_marked_payables() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Large Retailer", gstin="27ABCDE1234F1Z5")],
        suppliers=[Supplier(id="sup_transport", name="Transport Vendor", gstin="27TRANS1234F1Z5")],
        invoices=[
            Invoice(
                id="inv_prior",
                invoice_number="INV-PRIOR",
                customer_id="cust_1",
                date=date(2026, 4, 15),
                amount=4950000,
                taxable_value=4950000,
                tax_amount=0,
                status="paid",
            ),
            Invoice(
                id="inv_current",
                invoice_number="INV-CURRENT",
                customer_id="cust_1",
                date=date(2026, 5, 10),
                amount=100000,
                taxable_value=100000,
                tax_amount=0,
                status="open",
            ),
        ],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_transport",
                supplier_id="sup_transport",
                supplier_gstin="27TRANS1234F1Z5",
                invoice_number="TRN-1",
                date=date(2026, 5, 12),
                taxable_value=100000,
                tax_amount=18000,
                tds_section="194C",
                tds_rate_percent=1.0,
                status="booked",
            )
        ],
    )
    approvals = ApprovalService(repo)

    computation = prepare_tds_tcs_computation(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        period="2026-05",
        fiscal_year_start=date(2026, 4, 1),
        requested_by="accountant",
    )

    assert computation["mode"] == "local_contract_mock"
    assert computation["status"] == "approval_required"
    assert computation["summary"] == {
        "tcs_customers": 1,
        "tcs_amount": 50.0,
        "tds_payables": 1,
        "tds_amount": 1000.0,
        "total_withholding_review": 1050.0,
        "validation_errors": 0,
    }
    assert computation["tcs_rows"] == [
        {
            "customer_id": "cust_1",
            "customer_name": "Large Retailer",
            "section": "206C(1H)",
            "current_period_taxable_sales": 100000.0,
            "fy_taxable_sales": 5050000.0,
            "threshold": 5000000.0,
            "taxable_for_tcs": 50000.0,
            "rate_percent": 0.1,
            "tcs_amount": 50.0,
        }
    ]
    assert computation["tds_rows"] == [
        {
            "purchase_invoice_id": "pinv_transport",
            "supplier_id": "sup_transport",
            "supplier_name": "Transport Vendor",
            "section": "194C",
            "tds_base_amount": 100000.0,
            "rate_percent": 1.0,
            "tds_amount": 1000.0,
        }
    ]
    assert computation["audit"] == {
        "requested_by": "accountant",
        "external_income_tax_portal_called": False,
        "challan_payment_performed": False,
        "statutory_filing_performed": False,
        "limitation": "Local TDS/TCS computation review only; no income-tax portal, challan payment, TRACES, or statutory filing integration was called.",
    }
    assert repo.list_pending_approvals()[0].type == "review_tds_tcs_computation"


def test_should_report_no_tds_tcs_review_when_thresholds_and_markers_do_not_apply() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Small Retailer")],
        invoices=[
            Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", date=date(2026, 5, 10), amount=10000, taxable_value=10000, tax_amount=0)
        ],
    )

    computation = prepare_tds_tcs_computation(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        period="2026-05",
        fiscal_year_start=date(2026, 4, 1),
        requested_by="accountant",
    )

    assert computation["status"] == "no_withholding_review_needed"
    assert computation["summary"]["total_withholding_review"] == 0.0
    assert repo.list_pending_approvals() == []
