from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import PurchaseInvoice, Supplier
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.itc_reconciliation import reconcile_itc_2b


def test_should_match_booked_purchase_invoice_to_local_2b_entry_with_approval_audit() -> None:
    repo = InMemoryRepository()
    repo.upsert_supplier(Supplier(id="sup_soap", name="Soap Principal", gstin="27PRINC1234F1Z5"))
    repo.upsert_purchase_invoice(
        PurchaseInvoice(
            id="pinv_1",
            supplier_id="sup_soap",
            supplier_gstin="27PRINC1234F1Z5",
            invoice_number="PUR-1",
            date=date(2026, 5, 4),
            taxable_value=10000,
            tax_amount=1800,
            status="booked",
        )
    )
    approvals = ApprovalService(repo)

    result = reconcile_itc_2b(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        period="2026-05",
        portal_entries=[
            {
                "supplier_gstin": "27PRINC1234F1Z5",
                "invoice_number": "PUR-1",
                "invoice_date": date(2026, 5, 4),
                "taxable_value": 10000,
                "tax_amount": 1800,
                "itc_eligible": True,
            }
        ],
        requested_by="accountant",
    )

    assert approvals.requires_approval("review_itc_reconciliation") is True
    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "approval_required"
    assert result["summary"] == {
        "matched": 1,
        "amount_mismatches": 0,
        "missing_in_2b": 0,
        "extra_in_2b": 0,
        "eligible_itc_amount": 1800.0,
        "disputed_itc_amount": 0.0,
    }
    assert result["matches"][0]["purchase_invoice_id"] == "pinv_1"
    assert result["matches"][0]["supplier_name"] == "Soap Principal"
    assert result["audit"]["external_fetch_performed"] is False
    assert result["audit"]["limitation"] == "Local ITC/2B reconciliation contract only; no GSTN 2A/2B API was called."

    approval = repo.list_pending_approvals()[0]
    assert approval.type == "review_itc_reconciliation"
    assert approval.data["period"] == "2026-05"
    assert approval.data["summary"] == result["summary"]


def test_should_surface_2b_mismatches_missing_booked_invoices_and_extra_portal_entries() -> None:
    repo = InMemoryRepository()
    repo.upsert_supplier(Supplier(id="sup_soap", name="Soap Principal", gstin="27PRINC1234F1Z5"))
    repo.upsert_supplier(Supplier(id="sup_food", name="Food Principal", gstin="27FOODX1234F1Z5"))
    repo.upsert_purchase_invoice(
        PurchaseInvoice(
            id="pinv_mismatch",
            supplier_id="sup_soap",
            supplier_gstin="27PRINC1234F1Z5",
            invoice_number="PUR-MISMATCH",
            date=date(2026, 5, 8),
            taxable_value=10000,
            tax_amount=1800,
            status="booked",
        )
    )
    repo.upsert_purchase_invoice(
        PurchaseInvoice(
            id="pinv_missing",
            supplier_id="sup_food",
            supplier_gstin="27FOODX1234F1Z5",
            invoice_number="PUR-MISSING",
            date=date(2026, 5, 9),
            taxable_value=5000,
            tax_amount=900,
            status="booked",
        )
    )

    result = reconcile_itc_2b(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        period="2026-05",
        portal_entries=[
            {
                "supplier_gstin": "27PRINC1234F1Z5",
                "invoice_number": "PUR-MISMATCH",
                "invoice_date": date(2026, 5, 8),
                "taxable_value": 10000,
                "tax_amount": 1700,
                "itc_eligible": True,
            },
            {
                "supplier_gstin": "27EXTRA1234F1Z5",
                "invoice_number": "PUR-EXTRA",
                "invoice_date": date(2026, 5, 10),
                "taxable_value": 3000,
                "tax_amount": 540,
                "itc_eligible": True,
            },
        ],
        requested_by="accountant",
    )

    assert result["summary"] == {
        "matched": 0,
        "amount_mismatches": 1,
        "missing_in_2b": 1,
        "extra_in_2b": 1,
        "eligible_itc_amount": 0.0,
        "disputed_itc_amount": 2700.0,
    }
    assert result["mismatches"] == [
        {
            "purchase_invoice_id": "pinv_mismatch",
            "supplier_gstin": "27PRINC1234F1Z5",
            "invoice_number": "PUR-MISMATCH",
            "book_tax_amount": 1800.0,
            "portal_tax_amount": 1700.0,
            "code": "tax_amount_mismatch",
        }
    ]
    assert result["missing_in_2b"][0]["purchase_invoice_id"] == "pinv_missing"
    assert result["extra_in_2b"][0]["supplier_gstin"] == "27EXTRA1234F1Z5"


def test_should_persist_purchase_invoice_records_for_local_itc_review(tmp_path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    repo.upsert_supplier(Supplier(id="sup_soap", name="Soap Principal", gstin="27PRINC1234F1Z5"))
    repo.upsert_purchase_invoice(
        PurchaseInvoice(
            id="pinv_1",
            supplier_id="sup_soap",
            supplier_gstin="27PRINC1234F1Z5",
            invoice_number="PUR-1",
            date=date(2026, 5, 4),
            taxable_value=10000,
            tax_amount=1800,
        )
    )

    reloaded = JsonClientRepository(tmp_path / "data")

    assert reloaded.get_suppliers()[0].gstin == "27PRINC1234F1Z5"
    assert reloaded.get_purchase_invoices()[0].invoice_number == "PUR-1"
