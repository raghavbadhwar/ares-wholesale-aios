from __future__ import annotations

from datetime import date
import json
from pathlib import Path

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.cli import main
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import Customer, Invoice, InvoiceLineItem
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.profiles import ClientProfile, write_client_profile
from apps.ares.ares.workflows.gstr1 import prepare_gstr1_return


def test_prepare_gstr1_return_builds_b2b_and_hsn_surfaces_with_approval() -> None:
    repo = InMemoryRepository.from_records(
        customers=[
            Customer(id="cust_raj", name="Raj Traders", gstin="27ABCDE1234F1Z5", location="MH"),
            Customer(id="cust_delhi", name="Delhi Retail", gstin="07ABCDE1234F1Z5", location="DL"),
        ],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_raj",
                date=date(2026, 5, 21),
                amount=11800,
                taxable_value=10000,
                tax_amount=1800,
                gst_rate_percent=18,
                cgst_amount=900,
                sgst_amount=900,
                status="open",
                line_items=[
                    InvoiceLineItem(
                        description="Soap Case",
                        hsn_code="3401",
                        quantity=10,
                        unit="BOX",
                        taxable_value=10000,
                        gst_rate_percent=18,
                        cgst_amount=900,
                        sgst_amount=900,
                    )
                ],
            ),
            Invoice(
                id="inv_2",
                invoice_number="INV-2",
                customer_id="cust_delhi",
                date=date(2026, 5, 22),
                amount=5900,
                taxable_value=5000,
                tax_amount=900,
                gst_rate_percent=18,
                igst_amount=900,
                status="paid",
                line_items=[
                    InvoiceLineItem(
                        description="Vim Bar",
                        hsn_code="3405",
                        quantity=5,
                        unit="BOX",
                        taxable_value=5000,
                        gst_rate_percent=18,
                        igst_amount=900,
                    )
                ],
            ),
        ],
    )
    approvals = ApprovalService(repo)

    draft = prepare_gstr1_return(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        period="2026-05",
        seller_gstin="27AACCA1234A1Z9",
        requested_by="owner",
    )

    assert approvals.requires_approval("prepare_gstr1_return") is True
    assert draft["mode"] == "local_contract_mock"
    assert draft["status"] == "approval_required"
    assert draft["summary"] == {
        "b2b_invoices": 2,
        "b2cl_invoices": 0,
        "b2cs_groups": 0,
        "hsn_rows": 2,
        "taxable_value": 15000.0,
        "tax_amount": 2700.0,
        "validation_errors": 0,
    }
    assert draft["tables"]["b2b"][0]["recipient_gstin"] == "27ABCDE1234F1Z5"
    assert draft["tables"]["b2b"][0]["place_of_supply"] == "27"
    assert draft["tables"]["b2b"][0]["central_tax"] == 900.0
    assert draft["tables"]["b2b"][1]["integrated_tax"] == 900.0
    assert draft["tables"]["hsn"][0]["hsn_code"] == "3401"
    assert draft["tables"]["hsn"][0]["taxable_value"] == 10000.0
    assert draft["audit"]["external_submit_performed"] is False
    assert draft["audit"]["limitation"] == "Local GSTR-1 preparation payload only; no GSTN filing or API call was performed."

    approval = repo.list_pending_approvals()[0]
    assert approval.type == "prepare_gstr1_return"
    assert approval.data["period"] == "2026-05"
    assert approval.data["summary"]["b2b_invoices"] == 2
    assert approval.data["tables"]["b2b"][0]["invoice_number"] == "INV-1"
    assert approval.data["tables"]["hsn"][1]["hsn_code"] == "3405"
    assert approval.data["audit"]["external_submit_performed"] is False


def test_prepare_gstr1_return_groups_unregistered_sales_and_flags_missing_tax_fields() -> None:
    repo = InMemoryRepository.from_records(
        customers=[
            Customer(id="cust_cash", name="Cash Counter", location="27"),
            Customer(id="cust_unknown_state", name="Unknown State Buyer"),
        ],
        invoices=[
            Invoice(
                id="inv_b2cs",
                invoice_number="INV-B2CS",
                customer_id="cust_cash",
                date=date(2026, 5, 10),
                amount=1180,
                taxable_value=1000,
                tax_amount=180,
                gst_rate_percent=18,
                cgst_amount=90,
                sgst_amount=90,
                status="open",
            ),
            Invoice(
                id="inv_bad",
                invoice_number="INV-BAD",
                customer_id="cust_unknown_state",
                date=date(2026, 5, 11),
                amount=500,
                status="open",
            ),
        ],
    )

    draft = prepare_gstr1_return(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        period="2026-05",
        seller_gstin="27AACCA1234A1Z9",
        requested_by="owner",
    )

    assert draft["tables"]["b2cs"] == [
        {
            "place_of_supply": "27",
            "rate_percent": 18.0,
            "taxable_value": 1000.0,
            "integrated_tax": 0.0,
            "central_tax": 90.0,
            "state_tax": 90.0,
            "cess_amount": 0.0,
        }
    ]
    assert draft["summary"]["b2cs_groups"] == 1
    assert draft["summary"]["validation_errors"] == 3
    assert {"invoice_id": "inv_bad", "code": "place_of_supply_missing"} in draft["validation_errors"]
    assert {"invoice_id": "inv_bad", "code": "taxable_value_missing"} in draft["validation_errors"]
    assert {"invoice_id": "inv_bad", "code": "gst_rate_missing"} in draft["validation_errors"]


def test_prepare_gstr1_return_derives_component_tax_from_total_tax_when_components_are_missing() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_raj", name="Raj Traders", gstin="27ABCDE1234F1Z5", location="MH")],
        invoices=[
            Invoice(
                id="inv_derived",
                invoice_number="INV-DERIVED",
                customer_id="cust_raj",
                date=date(2026, 5, 12),
                amount=1180,
                taxable_value=1000,
                tax_amount=180,
                gst_rate_percent=18,
                status="open",
            )
        ],
    )

    draft = prepare_gstr1_return(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        period="2026-05",
        seller_gstin="27AACCA1234A1Z9",
        requested_by="owner",
    )

    assert draft["summary"]["tax_amount"] == 180.0
    assert draft["tables"]["b2b"][0]["central_tax"] == 90.0
    assert draft["tables"]["b2b"][0]["state_tax"] == 90.0
    assert draft["tables"]["b2b"][0]["integrated_tax"] == 0.0


def test_cli_prepare_gstr1_returns_json_and_persists_pending_approval(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    data_dir = tmp_path / ".ares" / "clients" / "demo" / "data"
    repo = JsonClientRepository(data_dir)
    repo.upsert_customer(Customer(id="cust_raj", name="Raj Traders", gstin="27ABCDE1234F1Z5"))
    repo.upsert_invoice(
        Invoice(
            id="inv_1",
            invoice_number="INV-1",
            customer_id="cust_raj",
            date=date(2026, 5, 21),
            amount=11800,
            taxable_value=10000,
            tax_amount=1800,
            gst_rate_percent=18,
            cgst_amount=900,
            sgst_amount=900,
            status="open",
        )
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "ares",
            "prepare-gstr1",
            "--client",
            "demo",
            "--period",
            "2026-05",
            "--seller-gstin",
            "27AACCA1234A1Z9",
            "--json",
        ],
    )

    assert main() == 0
    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["b2b_invoices"] == 1
    assert output["audit"]["external_submit_performed"] is False

    reloaded = JsonClientRepository(data_dir)
    pending = reloaded.list_pending_approvals()[0]
    assert pending.type == "prepare_gstr1_return"
    assert pending.data["tables"]["b2b"][0]["invoice_number"] == "INV-1"
