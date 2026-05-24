from __future__ import annotations

import hashlib
import hmac
import json
from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.supplier_payment_sandbox import (
    SUPPLIER_PAYMENT_SANDBOX_ADAPTER_LIMITATION,
    SUPPLIER_PAYMENT_SANDBOX_HEALTHCHECK_LIMITATION,
    SUPPLIER_PAYMENT_SANDBOX_PROOF_LIMITATION,
    build_supplier_payment_sandbox_healthcheck,
    ingest_supplier_payment_sandbox_payload,
)
from apps.ares.ares.data.models import PurchaseInvoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.supplier_payments import LOCAL_SUPPLIER_PAYMENT_LIMITATION


def _upi_signature(payload: dict[str, object], secret: str) -> dict[str, str]:
    canonical_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), canonical_payload, hashlib.sha256).hexdigest()
    return {"x-upi-signature": signature}


def test_should_route_verified_bank_transfer_supplier_settlement_fixture_through_local_contract() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=8000,
                tax_amount=1440,
                status="booked",
            )
        ]
    )
    payload = {
        "event": "supplier_payment.settled",
        "payload_reference": "fixture://supplier-bank/1",
        "contains_redacted_test_data": True,
        "settlement": {
            "id": "sup_settle_1",
            "supplier_id": "sup_soap",
            "purchase_invoice_id": "pinv_1",
            "amount": 9440,
            "utr": "NEFT-SUP-1",
            "settled_on": "2026-05-23",
            "status": "posted",
        },
    }

    result = ingest_supplier_payment_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="bank_transfer",
        payload=payload,
    )

    assert result["status"] == "reconciled"
    assert result["supplier_payment"]["matched_purchase_invoice_id"] == "pinv_1"
    assert result["supplier_payment"]["signature_verification_status"] == "verified_contract_fixture"
    assert result["provider_payload"]["payment_id"] == "sup_settle_1"
    assert result["adapter"]["connector"] == "supplier_payment_sandbox"
    assert result["adapter"]["provider"] == "bank_transfer"
    assert result["adapter"]["signature_verified"] is True
    assert result["adapter"]["limitation"] == SUPPLIER_PAYMENT_SANDBOX_ADAPTER_LIMITATION
    assert result["adapter"]["workflow_limitation"] == LOCAL_SUPPLIER_PAYMENT_LIMITATION
    assert result["audit"] == {
        "provider": "bank_transfer",
        "live_webhook_received": False,
        "webhook_signature_verified": True,
        "provider_api_called": False,
        "bank_execution_performed": False,
        "supplier_payment_record_created": True,
        "limitation": LOCAL_SUPPLIER_PAYMENT_LIMITATION,
    }
    assert repo.effective_purchase_invoice_projection(repo.get_purchase_invoices()[0])["status"] == "paid"
    assert repo.get_supplier_payments()[0].external_event_id == "sup_settle_1"
    assert result["proof_transcript"]["proof_safe"] is True
    assert result["proof_transcript"]["signature_verified"] is True
    assert result["proof_transcript"]["limitation"] == SUPPLIER_PAYMENT_SANDBOX_PROOF_LIMITATION


def test_should_route_nested_bank_transfer_export_payload_without_explicit_event_type() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=8000,
                tax_amount=1440,
                status="booked",
            )
        ]
    )
    payload = {
        "payload_reference": "fixture://supplier-bank/nested-export",
        "contains_redacted_test_data": True,
        "data": {
            "transfer": {
                "settlement_id": "sup_settle_nested_1",
                "beneficiary_id": "sup_soap",
                "invoice_ref": "pinv_1",
                "amount_minor": 944000,
                "bank_reference": "NEFT-SUP-NESTED-1",
                "settled_at": "2026-05-23T15:45:00Z",
                "state": "SETTLED",
            }
        },
    }

    result = ingest_supplier_payment_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="bank_transfer",
        payload=payload,
    )

    assert result["status"] == "reconciled"
    assert result["event_type"] == "settlement.posted"
    assert result["provider_payload"]["payment_id"] == "sup_settle_nested_1"
    assert result["provider_payload"]["payment_status"] == "settled"
    assert result["supplier_payment"]["reference"] == "NEFT-SUP-NESTED-1"
    assert result["supplier_payment"]["matched_purchase_invoice_id"] == "pinv_1"
    assert repo.get_supplier_payments()[0].amount == 9440.0


def test_should_block_signature_mismatch_for_upi_collect_without_mutating_purchase_invoice() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=8000,
                tax_amount=1440,
                status="booked",
            )
        ]
    )
    payload = {
        "type": "payment.success",
        "payload_reference": "fixture://supplier-upi/1",
        "contains_redacted_test_data": True,
        "data": {
            "payment": {
                "id": "sup_upi_1",
                "supplier_id": "sup_soap",
                "purchase_invoice_id": "pinv_1",
                "amount": 9440,
                "utr": "UPI-SUP-1",
                "paid_at": "2026-05-23T10:15:00Z",
                "status": "SUCCESS",
            }
        },
    }

    result = ingest_supplier_payment_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="upi_collect",
        payload=payload,
        headers={"x-upi-signature": "mismatch"},
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "blocked_unverified_signature"
    assert result["supplier_payment"]["matched_purchase_invoice_id"] is None
    assert result["supplier_payment"]["signature_verification_status"] == "not_verified_contract_mock"
    assert result["adapter"]["signature_verified"] is False
    assert repo.effective_purchase_invoice_projection(repo.get_purchase_invoices()[0])["status"] == "booked"
    assert repo.get_supplier_payments()[0].status == "blocked_unverified_signature"


def test_should_route_root_level_upi_collect_payload_without_explicit_type() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=8000,
                tax_amount=1440,
                status="booked",
            )
        ]
    )
    payload = {
        "payload_reference": "fixture://supplier-upi/root-level",
        "contains_redacted_test_data": True,
        "payment": {
            "payment_id": "sup_upi_root_1",
            "supplier": "sup_soap",
            "invoice_ref": "pinv_1",
            "amount_minor": 944000,
            "rrn": "UPI-SUP-ROOT-1",
            "settled_at": "2026-05-23T12:30:00Z",
            "state": "SUCCESS",
        },
    }
    headers = _upi_signature(payload, "sandbox_signature_key")

    result = ingest_supplier_payment_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="upi_collect",
        payload=payload,
        headers=headers,
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "reconciled"
    assert result["event_type"] == "payment.success"
    assert result["adapter"]["signature_verified"] is True
    assert result["provider_payload"]["payment_id"] == "sup_upi_root_1"
    assert result["provider_payload"]["payment_status"] == "success"
    assert result["supplier_payment"]["reference"] == "UPI-SUP-ROOT-1"
    assert repo.get_supplier_payments()[0].amount == 9440.0


def test_should_ignore_failed_supplier_payment_event_even_when_signature_verifies() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=8000,
                tax_amount=1440,
                status="booked",
            )
        ]
    )
    payload = {
        "type": "payment.failed",
        "payload_reference": "fixture://supplier-upi/failed",
        "contains_redacted_test_data": True,
        "data": {
            "payment": {
                "id": "sup_upi_fail_1",
                "supplier_id": "sup_soap",
                "purchase_invoice_id": "pinv_1",
                "amount": 9440,
                "utr": "UPI-SUP-FAIL-1",
                "paid_at": "2026-05-23T10:15:00Z",
                "status": "FAILED",
            }
        },
    }

    result = ingest_supplier_payment_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="upi_collect",
        payload=payload,
        headers=_upi_signature(payload, "sandbox_signature_key"),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "ignored_non_success_event"
    assert result["supplier_payment"] is None
    assert result["adapter"]["signature_verified"] is True
    assert result["audit"]["supplier_payment_record_created"] is False
    assert repo.effective_purchase_invoice_projection(repo.get_purchase_invoices()[0])["status"] == "booked"
    assert repo.get_supplier_payments() == []


def test_should_ignore_duplicate_supplier_payment_replay_after_first_verified_ingest() -> None:
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_1",
                supplier_id="sup_soap",
                invoice_number="PINV-1",
                taxable_value=8000,
                tax_amount=1440,
                status="booked",
            )
        ]
    )
    payload = {
        "type": "payment.success",
        "payload_reference": "fixture://supplier-upi/dup",
        "contains_redacted_test_data": True,
        "data": {
            "payment": {
                "id": "sup_upi_dup_1",
                "supplier_id": "sup_soap",
                "purchase_invoice_id": "pinv_1",
                "amount": 9440,
                "utr": "UPI-SUP-DUP-1",
                "paid_at": "2026-05-23T10:15:00Z",
                "status": "SUCCESS",
            }
        },
    }
    headers = _upi_signature(payload, "sandbox_signature_key")

    first = ingest_supplier_payment_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="upi_collect",
        payload=payload,
        headers=headers,
        webhook_signing_secret="sandbox_signature_key",
    )
    duplicate = ingest_supplier_payment_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="upi_collect",
        payload=payload,
        headers=headers,
        webhook_signing_secret="sandbox_signature_key",
    )

    assert first["status"] == "reconciled"
    assert duplicate["status"] == "reconciled"
    assert duplicate["supplier_payment"]["supplier_payment_id"] == first["supplier_payment"]["supplier_payment_id"]
    assert len(repo.get_supplier_payments()) == 1


def test_should_report_supplier_payment_sandbox_healthcheck_without_contacting_provider() -> None:
    result = build_supplier_payment_sandbox_healthcheck(
        provider="upi_collect",
        configured_env_names={"SUPPLIER_UPI_SANDBOX_WEBHOOK_SECRET"},
        safe_test_environment_confirmed=True,
    )

    assert result["status"] == "ready_for_local_adapter_tests"
    assert result["required_env_names"] == ["SUPPLIER_UPI_SANDBOX_WEBHOOK_SECRET"]
    assert result["missing_env_names"] == []
    assert result["webhook_signature_scheme"] == "hmac_sha256"
    assert result["can_run_local_adapter_tests"] is True
    assert result["audit"]["limitation"] == SUPPLIER_PAYMENT_SANDBOX_HEALTHCHECK_LIMITATION


def test_should_verify_upi_collect_signature_with_env_fallback(monkeypatch) -> None:
    monkeypatch.setenv("SUPPLIER_UPI_SANDBOX_WEBHOOK_SECRET", "env_fallback_secret_key")
    repo = InMemoryRepository.from_records(
        purchase_invoices=[
            PurchaseInvoice(
                id="pinv_env_1",
                supplier_id="sup_soap",
                invoice_number="PINV-ENV-1",
                taxable_value=8000,
                tax_amount=1440,
                status="booked",
            )
        ]
    )
    payload = {
        "payload_reference": "fixture://supplier-upi/root-level",
        "contains_redacted_test_data": True,
        "payment": {
            "payment_id": "sup_upi_env_1",
            "supplier": "sup_soap",
            "invoice_ref": "pinv_env_1",
            "amount_minor": 944000,
            "rrn": "UPI-SUP-ENV-1",
            "settled_at": "2026-05-23T12:30:00Z",
            "state": "SUCCESS",
        },
    }
    headers = _upi_signature(payload, "env_fallback_secret_key")

    result = ingest_supplier_payment_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="upi_collect",
        payload=payload,
        headers=headers,
        webhook_signing_secret=None,
    )

    assert result["status"] == "reconciled"
    assert result["adapter"]["signature_verified"] is True
    assert result["supplier_payment"]["signature_verification_status"] == "verified_contract_fixture"

