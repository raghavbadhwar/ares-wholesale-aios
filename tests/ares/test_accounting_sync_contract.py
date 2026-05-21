from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, Payment, StockRecord
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.accounting_sync import (
    import_accounting_sync_status,
    prepare_accounting_sync_export,
)


def test_should_prepare_local_tally_export_contract_with_approval_and_audit_metadata() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_raj", name="Raj Traders", gstin="27ABCDE1234F1Z5", location="MH")],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_raj",
                date=date(2026, 5, 21),
                amount=11800,
                tax_amount=1800,
                status="open",
            )
        ],
        payments=[
            Payment(
                id="pay_1",
                customer_id="cust_raj",
                amount=11800,
                date=date(2026, 5, 21),
                mode="upi",
                reference="UTR123",
                matched_invoice_id="inv_1",
                status="reconciled",
                audit_note="Exact party and amount match reconciled locally.",
            )
        ],
        stock_records=[
            StockRecord(sku_id="sku_soap", name="Soap Case", current_stock=24, reorder_level=10, unit="case")
        ],
    )
    approvals = ApprovalService(repo)

    batch = prepare_accounting_sync_export(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        system="tally",
        requested_by="owner",
    )

    assert approvals.requires_approval("export_accounting_sync") is True
    assert batch["mode"] == "local_contract_mock"
    assert batch["system"] == "tally"
    assert batch["status"] == "approval_required"
    assert batch["summary"] == {"parties": 1, "invoices": 1, "payments": 1, "stock_items": 1}
    assert batch["payload"]["parties"][0]["ledger_name"] == "Raj Traders"
    assert batch["payload"]["invoices"][0]["voucher_type"] == "Sales"
    assert batch["payload"]["invoices"][0]["party_ledger_id"] == "cust_raj"
    assert batch["payload"]["payments"][0]["against_invoice_id"] == "inv_1"
    assert batch["payload"]["stock_items"][0]["item_name"] == "Soap Case"
    assert batch["audit"]["requested_by"] == "owner"
    assert batch["audit"]["external_write_performed"] is False
    assert batch["audit"]["limitation"] == "Local contract payload only; no live Tally/Busy connector was called."

    approval = repo.list_pending_approvals()[0]
    assert approval.type == "export_accounting_sync"
    assert approval.data["batch_id"] == batch["batch_id"]
    assert approval.data["system"] == "tally"


def test_should_import_busy_style_sync_status_as_audit_only_without_mutating_ledgers() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_raj", amount=11800, status="open")],
        payments=[Payment(id="pay_1", customer_id="cust_raj", amount=11800, status="reconciled")],
    )

    result = import_accounting_sync_status(
        repository=repo,
        client_id="demo",
        system="busy",
        status_payload={
            "batch_id": "sync_123",
            "status": "accepted",
            "external_reference": "BUSY-IMPORT-99",
            "items": [
                {"record_type": "invoice", "record_id": "inv_1", "status": "accepted"},
                {"record_type": "payment", "record_id": "pay_1", "status": "accepted"},
            ],
        },
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "accepted"
    assert result["items"][0]["record_type"] == "invoice"
    assert repo.get_invoices()[0].status == "open"
    assert repo.get_payments()[0].status == "reconciled"
    assert repo.list_action_logs()[0].action_type == "import_accounting_sync_status"
    assert repo.list_action_logs()[0].result["external_reference"] == "BUSY-IMPORT-99"
