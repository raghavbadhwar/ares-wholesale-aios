from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import BusinessGSTRegistration, Customer, Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.composition_scheme import review_composition_scheme_guard


def test_should_block_composition_scheme_invoice_when_tax_is_collected_or_supply_is_interstate() -> None:
    repo = InMemoryRepository.from_records(
        business_gst_registrations=[
            BusinessGSTRegistration(
                id="gst_comp",
                gstin="27AACCA1234A1Z9",
                legal_name="Composition Distributor",
                state_code="27",
                state_name="Maharashtra",
                composition_scheme=True,
                is_default=True,
            )
        ],
        customers=[Customer(id="cust_dl", name="Delhi Buyer", gstin="07ABCDE1234F1Z5", location="DL")],
        invoices=[
            Invoice(
                id="inv_bad",
                invoice_number="INV-BAD",
                customer_id="cust_dl",
                business_gstin_id="gst_comp",
                date=date(2026, 5, 21),
                amount=1180,
                taxable_value=1000,
                tax_amount=180,
                gst_rate_percent=18,
                status="open",
            )
        ],
    )
    approvals = ApprovalService(repo)

    guard = review_composition_scheme_guard(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        invoice=repo.get_invoices()[0],
        fiscal_year_start=date(2026, 4, 1),
        requested_by="accountant",
    )

    assert guard["mode"] == "local_contract_mock"
    assert guard["status"] == "blocked_for_review"
    assert guard["summary"] == {"violations": 2, "warnings": 0}
    assert guard["allowed_document_type"] == "bill_of_supply"
    assert guard["violations"] == [
        {"invoice_id": "inv_bad", "code": "composition_tax_collection_not_allowed"},
        {"invoice_id": "inv_bad", "code": "composition_inter_state_supply_not_allowed", "place_of_supply": "07", "registration_state": "27"},
    ]
    assert guard["audit"] == {
        "requested_by": "accountant",
        "external_gstn_validation_called": False,
        "accountant_certification_performed": False,
        "limitation": "Local composition-scheme guard only; no GSTN validation or accountant certification was performed.",
    }
    assert repo.list_pending_approvals()[0].type == "review_composition_scheme_guard"


def test_should_allow_clean_composition_bill_of_supply_without_approval() -> None:
    repo = InMemoryRepository.from_records(
        business_gst_registrations=[
            BusinessGSTRegistration(
                id="gst_comp",
                gstin="27AACCA1234A1Z9",
                legal_name="Composition Distributor",
                state_code="27",
                state_name="Maharashtra",
                composition_scheme=True,
                is_default=True,
            )
        ],
        customers=[Customer(id="cust_mh", name="Mumbai Buyer", gstin=None, location="MH")],
        invoices=[
            Invoice(
                id="inv_ok",
                invoice_number="BOS-1",
                customer_id="cust_mh",
                business_gstin_id="gst_comp",
                date=date(2026, 5, 21),
                amount=1000,
                taxable_value=1000,
                tax_amount=0,
                gst_rate_percent=0,
                invoice_type="bill_of_supply",
                status="open",
            )
        ],
    )

    guard = review_composition_scheme_guard(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        invoice=repo.get_invoices()[0],
        fiscal_year_start=date(2026, 4, 1),
        requested_by="accountant",
    )

    assert guard["status"] == "clear"
    assert guard["violations"] == []
    assert repo.list_pending_approvals() == []
