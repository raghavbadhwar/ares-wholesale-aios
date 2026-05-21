from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, InvoiceLineItem
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.eway_bill import prepare_eway_bill_draft


def test_should_prepare_local_eway_bill_payload_with_approval_and_audit() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_delhi", name="Delhi Retail", gstin="07ABCDE1234F1Z5", location="DL")],
        invoices=[
            Invoice(
                id="inv_eway",
                invoice_number="INV-EWAY",
                customer_id="cust_delhi",
                date=date(2026, 5, 18),
                amount=59000,
                taxable_value=50000,
                tax_amount=9000,
                gst_rate_percent=18,
                igst_amount=9000,
                line_items=[
                    InvoiceLineItem(
                        description="Soap Case",
                        hsn_code="3401",
                        quantity=25,
                        unit="BOX",
                        taxable_value=50000,
                        gst_rate_percent=18,
                        igst_amount=9000,
                    )
                ],
            )
        ],
    )
    approvals = ApprovalService(repo)

    draft = prepare_eway_bill_draft(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        invoice_id="inv_eway",
        seller_gstin="27AACCA1234A1Z9",
        dispatch={
            "from_pincode": "400001",
            "to_pincode": "110001",
            "distance_km": 1420,
            "transport_mode": "road",
            "transporter_name": "Fast Logistics",
            "vehicle_number": "MH01AB1234",
        },
        requested_by="dispatch_manager",
    )

    assert approvals.requires_approval("prepare_eway_bill") is True
    assert draft["mode"] == "local_contract_mock"
    assert draft["status"] == "approval_required"
    assert draft["summary"] == {"eway_bill_required": True, "validation_errors": 0, "invoice_value": 59000.0}
    assert draft["payload"]["document_number"] == "INV-EWAY"
    assert draft["payload"]["seller_gstin"] == "27AACCA1234A1Z9"
    assert draft["payload"]["buyer_gstin"] == "07ABCDE1234F1Z5"
    assert draft["payload"]["from_pincode"] == "400001"
    assert draft["payload"]["to_pincode"] == "110001"
    assert draft["payload"]["distance_km"] == 1420
    assert draft["payload"]["line_items"][0]["hsn_code"] == "3401"
    assert draft["audit"]["external_submit_performed"] is False
    assert draft["audit"]["limitation"] == "Local e-way bill preparation contract only; no NIC/GSTN API was called."

    approval = repo.list_pending_approvals()[0]
    assert approval.type == "prepare_eway_bill"
    assert approval.data["batch_id"] == draft["batch_id"]
    assert approval.data["invoice_id"] == "inv_eway"
    assert approval.data["summary"] == draft["summary"]


def test_should_flag_missing_eway_bill_fields_for_accountant_review() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_cash", name="Cash Buyer", location="MH")],
        invoices=[
            Invoice(
                id="inv_bad",
                invoice_number="INV-BAD",
                customer_id="cust_cash",
                date=date(2026, 5, 19),
                amount=75000,
                taxable_value=70000,
                tax_amount=5000,
                line_items=[
                    InvoiceLineItem(
                        description="Unclassified Goods",
                        taxable_value=70000,
                        quantity=1,
                        unit="LOT",
                    )
                ],
            )
        ],
    )

    draft = prepare_eway_bill_draft(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        invoice_id="inv_bad",
        seller_gstin="27AACCA1234A1Z9",
        dispatch={"from_pincode": "400001", "to_pincode": "400002", "transport_mode": "road"},
        requested_by="dispatch_manager",
    )

    assert draft["status"] == "needs_review"
    assert draft["summary"]["validation_errors"] == 4
    assert draft["validation_errors"] == [
        {"code": "buyer_gstin_missing"},
        {"code": "distance_km_missing"},
        {"code": "vehicle_number_missing"},
        {"code": "line_item_hsn_missing", "line": 1},
    ]
    assert repo.list_pending_approvals()[0].type == "prepare_eway_bill"


def test_should_mark_eway_bill_not_required_below_threshold_without_approval() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_raj", name="Raj Traders", gstin="27ABCDE1234F1Z5", location="MH")],
        invoices=[
            Invoice(
                id="inv_small",
                invoice_number="INV-SMALL",
                customer_id="cust_raj",
                date=date(2026, 5, 20),
                amount=40000,
                taxable_value=35000,
                tax_amount=5000,
            )
        ],
    )

    draft = prepare_eway_bill_draft(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        invoice_id="inv_small",
        seller_gstin="27AACCA1234A1Z9",
        dispatch={},
        requested_by="dispatch_manager",
    )

    assert draft["status"] == "not_required"
    assert draft["summary"] == {"eway_bill_required": False, "validation_errors": 0, "invoice_value": 40000.0}
    assert repo.list_pending_approvals() == []
