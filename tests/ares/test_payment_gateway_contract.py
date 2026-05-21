from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.payment_gateway import (
    LOCAL_PAYMENT_GATEWAY_LIMITATION,
    ingest_payment_gateway_webhook_contract,
    prepare_payment_gateway_link_contract,
)


def test_should_prepare_approval_gated_payment_link_contract_without_live_gateway_call() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    approvals = ApprovalService(repo)

    contract = prepare_payment_gateway_link_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        invoice_id="inv_1",
        provider="razorpay",
        requested_by="owner",
    )

    assert contract["mode"] == "local_contract_mock"
    assert contract["status"] == "approval_required"
    assert contract["request"]["provider"] == "razorpay"
    assert contract["request"]["invoice_id"] == "inv_1"
    assert contract["request"]["amount"] == 11800.0
    assert contract["request"]["currency"] == "INR"
    assert contract["request"]["supported_methods"] == ["upi", "card", "netbanking"]
    assert contract["audit"] == {
        "requested_by": "owner",
        "approval_required": True,
        "payment_gateway_api_called": False,
        "payment_link_created": False,
        "qr_code_generated": False,
        "autopay_setup": False,
        "bank_execution_performed": False,
        "limitation": LOCAL_PAYMENT_GATEWAY_LIMITATION,
    }
    assert repo.list_pending_approvals()[0].type == "create_payment_gateway_link"
    assert repo.list_action_logs()[0].action_type == "payment_gateway_link_contract"


def test_should_reconcile_local_payment_gateway_webhook_contract_without_live_webhook_claim() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )

    result = ingest_payment_gateway_webhook_contract(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="phonepe",
        webhook_event={
            "event_type": "payment.captured",
            "payment_id": "pgw_1",
            "invoice_id": "inv_1",
            "customer_id": "cust_1",
            "amount": 11800,
            "utr": "UTR-PGW-1",
            "paid_on": date(2026, 5, 21),
        },
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "reconciled"
    assert result["payment"]["matched_invoice_id"] == "inv_1"
    assert result["payment"]["status"] == "reconciled"
    assert result["audit"]["live_webhook_received"] is False
    assert result["audit"]["payment_gateway_api_called"] is False
    assert result["audit"]["limitation"] == LOCAL_PAYMENT_GATEWAY_LIMITATION
    assert repo.get_invoices()[0].status == "paid"
    assert repo.get_payments()[0].reference == "UTR-PGW-1"
    assert repo.list_action_logs()[-1].action_type == "payment_gateway_webhook_contract"
