from __future__ import annotations

from datetime import date

from apps.ares.ares.data.models import BusinessGSTRegistration, Customer, Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.multi_gstin import (
    build_multi_gstin_return_plan,
    resolve_invoice_gstin_context,
)


def test_should_resolve_invoice_to_correct_business_gstin_registration() -> None:
    repo = InMemoryRepository.from_records(
        business_gst_registrations=[
            BusinessGSTRegistration(
                id="gst_mh",
                gstin="27AACCA1234A1Z9",
                legal_name="Ares Distribution Maharashtra",
                state_code="27",
                state_name="Maharashtra",
                is_default=True,
            ),
            BusinessGSTRegistration(
                id="gst_dl",
                gstin="07AACCA1234A1Z7",
                legal_name="Ares Distribution Delhi",
                state_code="07",
                state_name="Delhi",
            ),
        ],
        customers=[Customer(id="cust_dl", name="Delhi Retail", gstin="07ABCDE1234F1Z5", location="DL")],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_dl",
                business_gstin_id="gst_mh",
                date=date(2026, 5, 21),
                amount=1180,
                taxable_value=1000,
                tax_amount=180,
                gst_rate_percent=18,
                status="open",
            )
        ],
    )

    context = resolve_invoice_gstin_context(repository=repo, invoice=repo.get_invoices()[0])

    assert context["mode"] == "local_contract_mock"
    assert context["selected_registration"] == {
        "id": "gst_mh",
        "gstin": "27AACCA1234A1Z9",
        "legal_name": "Ares Distribution Maharashtra",
        "state_code": "27",
        "state_name": "Maharashtra",
    }
    assert context["place_of_supply"] == "07"
    assert context["tax_mode"] == "inter_state"
    assert context["validation_errors"] == []
    assert context["audit"] == {
        "external_gstn_registration_validation_called": False,
        "filing_performed": False,
        "limitation": "Local multi-GSTIN management only; no GSTN registration validation or filing API was called.",
    }


def test_should_build_period_return_plan_grouped_by_business_gstin_and_flag_bad_links() -> None:
    repo = InMemoryRepository.from_records(
        business_gst_registrations=[
            BusinessGSTRegistration(id="gst_mh", gstin="27AACCA1234A1Z9", legal_name="MH Entity", state_code="27", state_name="Maharashtra", is_default=True),
            BusinessGSTRegistration(id="gst_dl", gstin="07AACCA1234A1Z7", legal_name="DL Entity", state_code="07", state_name="Delhi"),
            BusinessGSTRegistration(id="gst_inactive", gstin="29AACCA1234A1Z2", legal_name="KA Entity", state_code="29", state_name="Karnataka", status="inactive"),
        ],
        invoices=[
            Invoice(id="inv_mh", invoice_number="INV-MH", business_gstin_id="gst_mh", date=date(2026, 5, 1), amount=1180, taxable_value=1000, tax_amount=180, gst_rate_percent=18),
            Invoice(id="inv_dl", invoice_number="INV-DL", business_gstin_id="gst_dl", date=date(2026, 5, 2), amount=2360, taxable_value=2000, tax_amount=360, gst_rate_percent=18),
            Invoice(id="inv_bad", invoice_number="INV-BAD", business_gstin_id="gst_inactive", date=date(2026, 5, 3), amount=500, taxable_value=500, tax_amount=0, gst_rate_percent=0),
            Invoice(id="inv_default", invoice_number="INV-DEF", date=date(2026, 5, 4), amount=590, taxable_value=500, tax_amount=90, gst_rate_percent=18),
        ],
    )

    plan = build_multi_gstin_return_plan(repository=repo, period="2026-05")

    assert plan["mode"] == "local_contract_mock"
    assert plan["summary"] == {
        "active_registrations": 2,
        "invoice_count": 3,
        "taxable_value": 3500.0,
        "tax_amount": 630.0,
        "validation_errors": 1,
    }
    assert plan["registrations"] == [
        {
            "business_gstin_id": "gst_mh",
            "gstin": "27AACCA1234A1Z9",
            "state_code": "27",
            "invoice_ids": ["inv_mh", "inv_default"],
            "invoice_count": 2,
            "taxable_value": 1500.0,
            "tax_amount": 270.0,
        },
        {
            "business_gstin_id": "gst_dl",
            "gstin": "07AACCA1234A1Z7",
            "state_code": "07",
            "invoice_ids": ["inv_dl"],
            "invoice_count": 1,
            "taxable_value": 2000.0,
            "tax_amount": 360.0,
        },
    ]
    assert plan["validation_errors"] == [{"invoice_id": "inv_bad", "code": "business_gstin_inactive"}]
