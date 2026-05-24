from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, PurchaseInvoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.accounting_sync import prepare_accounting_sync_export
from apps.ares.ares.workflows.eway_bill import prepare_eway_bill_draft
from apps.ares.ares.workflows.gstn_api import prepare_gstn_api_exchange_contract
from apps.ares.ares.workflows.gstr1 import prepare_gstr1_return
from apps.ares.ares.workflows.itc_reconciliation import reconcile_itc_2b
from apps.ares.ares.workflows.payment_gateway import prepare_payment_gateway_link_contract
from apps.ares.ares.workflows.whatsapp_business import prepare_whatsapp_business_message


def test_should_dedupe_repeated_payment_gateway_link_contract_by_business_identity() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    approvals = ApprovalService(repo)

    first = prepare_payment_gateway_link_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        invoice_id="inv_1",
        provider="razorpay",
        requested_by="owner",
    )
    second = prepare_payment_gateway_link_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        invoice_id="inv_1",
        provider="razorpay",
        requested_by="owner",
    )

    assert first["approval_id"] == second["approval_id"]
    assert first["request"]["request_id"] == second["request"]["request_id"]
    assert len(repo.list_pending_approvals()) == 1


def test_should_dedupe_repeated_whatsapp_message_contract_without_explicit_key_when_payload_is_identical() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Ramesh Stores", phone="+919999999999")]
    )
    approvals = ApprovalService(repo)

    first = prepare_whatsapp_business_message(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        template_name="payment_reminder",
        body="Balance pending",
        requested_by="owner",
    )
    second = prepare_whatsapp_business_message(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        template_name="payment_reminder",
        body="Balance pending",
        requested_by="owner",
    )

    assert first["approval_id"] == second["approval_id"]
    assert first["idempotency_key"] == second["idempotency_key"]
    assert len(repo.list_pending_approvals()) == 1


def test_should_dedupe_repeated_gst_and_accounting_contracts_when_inputs_are_unchanged() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Raj Traders", gstin="27ABCDE1234F1Z5", phone="+919999999999")],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_1",
                date=date(2026, 5, 21),
                amount=11800,
                taxable_value=10000,
                tax_amount=1800,
                gst_rate_percent=18.0,
                place_of_supply="27",
                status="open",
            )
        ],
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_1",
                supplier_gstin="27SUPPLIER1234Z9",
                invoice_number="SUP-1",
                date=date(2026, 5, 10),
                taxable_value=10000,
                tax_amount=1800,
            )
        ],
    )
    approvals = ApprovalService(repo)

    first_sync = prepare_accounting_sync_export(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        system="tally",
        requested_by="owner",
    )
    second_sync = prepare_accounting_sync_export(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        system="tally",
        requested_by="owner",
    )
    assert first_sync["approval_id"] == second_sync["approval_id"]
    assert first_sync["batch_id"] == second_sync["batch_id"]

    first_gstr1 = prepare_gstr1_return(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        period="2026-05",
        seller_gstin="27SELLER1234F1Z5",
        requested_by="accountant",
    )
    second_gstr1 = prepare_gstr1_return(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        period="2026-05",
        seller_gstin="27SELLER1234F1Z5",
        requested_by="accountant",
    )
    assert first_gstr1["approval_id"] == second_gstr1["approval_id"]
    assert first_gstr1["batch_id"] == second_gstr1["batch_id"]

    first_itc = reconcile_itc_2b(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        period="2026-05",
        portal_entries=[
            {
                "supplier_gstin": "27SUPPLIER1234Z9",
                "invoice_number": "SUP-1",
                "invoice_date": "2026-05-10",
                "taxable_value": 10000,
                "tax_amount": 1800,
                "itc_eligible": True,
            }
        ],
        requested_by="accountant",
    )
    second_itc = reconcile_itc_2b(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        period="2026-05",
        portal_entries=[
            {
                "supplier_gstin": "27SUPPLIER1234Z9",
                "invoice_number": "SUP-1",
                "invoice_date": "2026-05-10",
                "taxable_value": 10000,
                "tax_amount": 1800,
                "itc_eligible": True,
            }
        ],
        requested_by="accountant",
    )
    assert first_itc["approval_id"] == second_itc["approval_id"]
    assert first_itc["batch_id"] == second_itc["batch_id"]


def test_should_dedupe_repeated_gstn_and_eway_contracts_when_inputs_are_unchanged() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Raj Traders", gstin="27ABCDE1234F1Z5")],
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_1",
                date=date(2026, 5, 21),
                amount=118000,
                taxable_value=100000,
                tax_amount=18000,
                gst_rate_percent=18.0,
                place_of_supply="27",
                status="open",
            )
        ],
    )
    approvals = ApprovalService(repo)

    first_gstn = prepare_gstn_api_exchange_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        operation="gstr1_return_upload",
        gstin="27SELLER1234F1Z5",
        requested_by="accountant",
        payload={"period": "2026-05", "sections": {"b2b": 1}},
    )
    second_gstn = prepare_gstn_api_exchange_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        operation="gstr1_return_upload",
        gstin="27SELLER1234F1Z5",
        requested_by="accountant",
        payload={"period": "2026-05", "sections": {"b2b": 1}},
    )
    assert first_gstn["approval_id"] == second_gstn["approval_id"]
    assert first_gstn["request"]["request_id"] == second_gstn["request"]["request_id"]

    dispatch = {
        "from_pincode": "400001",
        "to_pincode": "400002",
        "distance_km": 12,
        "transport_mode": "road",
        "vehicle_number": "MH12AB1234",
    }
    first_eway = prepare_eway_bill_draft(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        invoice_id="inv_1",
        seller_gstin="27SELLER1234F1Z5",
        dispatch=dispatch,
        requested_by="accountant",
    )
    second_eway = prepare_eway_bill_draft(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        invoice_id="inv_1",
        seller_gstin="27SELLER1234F1Z5",
        dispatch=dispatch,
        requested_by="accountant",
    )
    assert first_eway["approval_id"] == second_eway["approval_id"]
    assert first_eway["batch_id"] == second_eway["batch_id"]
