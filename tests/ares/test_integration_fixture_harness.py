from __future__ import annotations

import pytest

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, Payment
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.connectors.whatsapp_sandbox import (
    WHATSAPP_SANDBOX_ADAPTER_LIMITATION,
    build_whatsapp_sandbox_external_evidence_bundle,
    build_whatsapp_sandbox_proof_artifact_metadata,
    build_whatsapp_sandbox_proof_metadata_manifest,
    ingest_whatsapp_sandbox_webhook,
)
from apps.ares.ares.connectors.tally_sync_adapter import (
    build_tally_bridge_execution_harness,
    build_tally_bridge_external_evidence_bundle,
    build_tally_bridge_proof_artifact_metadata,
    build_tally_bridge_proof_metadata_manifest,
)
from apps.ares.ares.workflows.accounting_sync import (
    LOCAL_SYNC_LIMITATION,
    import_accounting_sync_status,
    normalize_accounting_bridge_payload,
)
from apps.ares.ares.connectors.proof_packets import (
    build_benchmark_external_evidence_bundle_packet,
    build_benchmark_proof_collection_packet,
)
from apps.ares.ares.connectors.gstn_sandbox import ingest_gst_sandbox_response, prepare_gst_sandbox_exchange
from apps.ares.ares.connectors.gstn_sandbox import (
    build_gst_sandbox_external_evidence_bundle,
    build_gst_sandbox_proof_artifact_metadata,
    build_gst_sandbox_proof_metadata_manifest,
)
from apps.ares.ares.connectors.payment_gateway_sandbox import (
    build_payment_gateway_sandbox_external_evidence_bundle,
    build_payment_gateway_sandbox_proof_artifact_metadata,
    build_payment_gateway_sandbox_proof_metadata_manifest,
    ingest_payment_gateway_sandbox_payload,
)
from apps.ares.ares.workflows.gstn_api import (
    GSTN_API_CONTRACT_LIMITATION,
    normalize_gstn_api_response_contract,
    prepare_gstn_api_exchange_contract,
)
from apps.ares.ares.workflows.payment_gateway import LOCAL_PAYMENT_GATEWAY_LIMITATION, ingest_payment_gateway_webhook_contract
from apps.ares.ares.workflows.whatsapp_business import (
    WHATSAPP_BUSINESS_LIMITATION,
    prepare_whatsapp_business_message,
    record_whatsapp_delivery_receipt,
)
from tests.ares.support import (
    assert_last_action_log,
    assert_local_contract_audit,
    assert_pending_approval,
    assert_redaction_safe_payload,
    build_cashfree_signature_header,
    build_phonepe_signature_header,
    build_razorpay_signature_header,
    build_whatsapp_signature_header,
    cashfree_failed_webhook_payload,
    cashfree_success_webhook_payload,
    gsp_manual_review_response,
    gsp_gstr2b_pull_response,
    gstn_gstr1_upload_response,
    gstn_validation_failed_response,
    gst_sandbox_external_evidence_bundle,
    gst_sandbox_proof_artifact,
    gst_sandbox_proof_manifest,
    payment_failed_webhook_event,
    payment_webhook_event,
    payment_gateway_sandbox_external_evidence_bundle,
    payment_gateway_sandbox_proof_artifact,
    payment_gateway_sandbox_proof_manifest,
    phonepe_failed_webhook_payload,
    phonepe_success_webhook_payload,
    proof_artifact_manifest,
    razorpay_captured_webhook_payload,
    razorpay_failed_webhook_payload,
    razorpay_refunded_webhook_payload,
    tally_odbc_manual_review_rows,
    tally_odbc_rows,
    tally_sandbox_external_evidence_bundle,
    tally_sandbox_proof_artifact,
    tally_sandbox_proof_manifest,
    tally_status_xml_text,
    tally_status_payload_from_xml,
    whatsapp_delivery_receipt_event,
    whatsapp_failed_delivery_receipt_event,
    whatsapp_inbound_message_payload,
    whatsapp_sandbox_external_evidence_bundle,
    whatsapp_sandbox_proof_artifact,
    whatsapp_sandbox_proof_manifest,
    whatsapp_status_webhook_payload,
)


@pytest.mark.parametrize(
    ("label", "factory"),
    [
        ("whatsapp_delivery_receipt", whatsapp_delivery_receipt_event),
        ("whatsapp_failed_delivery_receipt", whatsapp_failed_delivery_receipt_event),
        ("whatsapp_inbound_message_payload", whatsapp_inbound_message_payload),
        ("whatsapp_status_webhook_payload", whatsapp_status_webhook_payload),
        ("whatsapp_sandbox_external_evidence_bundle", whatsapp_sandbox_external_evidence_bundle),
        ("whatsapp_sandbox_proof_artifact", whatsapp_sandbox_proof_artifact),
        ("whatsapp_sandbox_proof_manifest", whatsapp_sandbox_proof_manifest),
        ("gstn_gstr1_upload_response", gstn_gstr1_upload_response),
        ("gsp_gstr2b_pull_response", gsp_gstr2b_pull_response),
        ("gstn_validation_failed_response", gstn_validation_failed_response),
        ("gsp_manual_review_response", gsp_manual_review_response),
        ("gst_sandbox_external_evidence_bundle", gst_sandbox_external_evidence_bundle),
        ("gst_sandbox_proof_artifact", gst_sandbox_proof_artifact),
        ("gst_sandbox_proof_manifest", gst_sandbox_proof_manifest),
        ("payment_webhook_event", payment_webhook_event),
        ("payment_failed_webhook_event", payment_failed_webhook_event),
        ("payment_gateway_sandbox_external_evidence_bundle", payment_gateway_sandbox_external_evidence_bundle),
        ("razorpay_captured_webhook_payload", razorpay_captured_webhook_payload),
        ("razorpay_failed_webhook_payload", razorpay_failed_webhook_payload),
        ("razorpay_refunded_webhook_payload", razorpay_refunded_webhook_payload),
        ("cashfree_success_webhook_payload", cashfree_success_webhook_payload),
        ("cashfree_failed_webhook_payload", cashfree_failed_webhook_payload),
        ("phonepe_success_webhook_payload", phonepe_success_webhook_payload),
        ("phonepe_failed_webhook_payload", phonepe_failed_webhook_payload),
        ("tally_odbc_manual_review_rows", tally_odbc_manual_review_rows),
        ("tally_odbc_rows", tally_odbc_rows),
        ("tally_status_xml_text", tally_status_xml_text),
        ("tally_status_payload_from_xml", tally_status_payload_from_xml),
        ("tally_sandbox_external_evidence_bundle", tally_sandbox_external_evidence_bundle),
        ("tally_sandbox_proof_artifact", tally_sandbox_proof_artifact),
        ("tally_sandbox_proof_manifest", tally_sandbox_proof_manifest),
        ("proof_artifact_manifest", proof_artifact_manifest),
        ("payment_gateway_sandbox_proof_artifact", payment_gateway_sandbox_proof_artifact),
        ("payment_gateway_sandbox_proof_manifest", payment_gateway_sandbox_proof_manifest),
    ],
)
def test_integration_fixtures_are_deterministic_and_redaction_safe(label: str, factory) -> None:
    first = factory()
    second = factory()

    assert first == second, label
    assert_redaction_safe_payload(first)


def test_redaction_guard_rejects_secret_like_fields() -> None:
    with pytest.raises(AssertionError, match="forbidden key fragment"):
        assert_redaction_safe_payload({"webhook_secret": "sandbox-placeholder"})


def test_whatsapp_sandbox_receipt_fixture_records_local_audit_without_live_claims() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Ramesh Stores", phone="+919000000001", preferred_language="marathi")]
    )
    approvals = ApprovalService(repo)
    draft = prepare_whatsapp_business_message(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        template_name="payment_reminder",
        body="Sandbox payment reminder",
        requested_by="owner",
        dedupe_key="waba:sandbox:receipt:1",
    )
    fixture = whatsapp_delivery_receipt_event()

    assert_pending_approval(
        repo,
        "send_whatsapp_business_message",
        expected_data={
            "channel": "whatsapp_business",
            "template_name": "payment_reminder",
            "recipient_phone": fixture["recipient_phone"],
        },
    )

    receipt = record_whatsapp_delivery_receipt(
        repository=repo,
        client_id=fixture["client_id"],
        approval_id=draft["approval_id"],
        provider_message_id=fixture["provider_message_id"],
        recipient_phone=fixture["recipient_phone"],
        status=fixture["status"],
    )

    assert receipt["delivery_status"] == "delivered"
    assert receipt["message_drop"] is False
    assert receipt["external_whatsapp_business_api_called"] is False
    assert receipt["limitation"] == WHATSAPP_BUSINESS_LIMITATION
    assert repo.list_action_logs()[-1].status == "executed"


def test_whatsapp_failed_delivery_fixture_marks_message_drop_without_live_claims() -> None:
    repo = InMemoryRepository()
    fixture = whatsapp_failed_delivery_receipt_event()

    receipt = record_whatsapp_delivery_receipt(
        repository=repo,
        client_id=fixture["client_id"],
        approval_id=fixture["approval_id"],
        provider_message_id=fixture["provider_message_id"],
        recipient_phone=fixture["recipient_phone"],
        status=fixture["status"],
    )

    assert receipt["delivery_status"] == "failed"
    assert receipt["message_drop"] is True
    assert receipt["limitation"] == WHATSAPP_BUSINESS_LIMITATION
    assert_last_action_log(repo, action_type="whatsapp_delivery_receipt", status="failed")


def test_whatsapp_signed_status_fixture_drives_adapter_and_delivery_sink_without_live_claims() -> None:
    repo = InMemoryRepository()
    payload = whatsapp_status_webhook_payload()

    result = ingest_whatsapp_sandbox_webhook(
        repository=repo,
        client_id="demo",
        payload=payload,
        headers=build_whatsapp_signature_header(payload),
        webhook_app_secret="sandbox_app_secret",
        approval_by_provider_message_id={"wamid.sandbox.msg.0001": "approval_demo_1"},
    )

    assert result["status"] == "parsed"
    assert len(result["delivery_updates"]) == 1
    assert len(result["delivery_receipts"]) == 1
    assert result["delivery_receipts"][0]["message_drop"] is False
    assert result["adapter"]["connector"] == "whatsapp_sandbox"
    assert result["adapter"]["delivery_sink_invoked"] is True
    assert result["adapter"]["limitation"] == WHATSAPP_SANDBOX_ADAPTER_LIMITATION
    assert result["proof_transcript"]["proof_safe"] is True
    assert repo.list_action_logs()[-1].approval_id == "approval_demo_1"


def test_whatsapp_proof_artifact_and_manifest_builders_match_proof_packet_contract() -> None:
    repo = InMemoryRepository()
    payload = whatsapp_status_webhook_payload()

    result = ingest_whatsapp_sandbox_webhook(
        repository=repo,
        client_id="demo",
        payload=payload,
        headers=build_whatsapp_signature_header(payload),
        webhook_app_secret="sandbox_app_secret",
        approval_by_provider_message_id={"wamid.sandbox.msg.0001": "approval_demo_1"},
    )
    artifact = build_whatsapp_sandbox_proof_artifact_metadata(
        adapter_result=result,
        run_timestamp="2026-05-23T11:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-2",
    )
    manifest = build_whatsapp_sandbox_proof_metadata_manifest(
        adapter_result=result,
        run_timestamp="2026-05-23T11:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-2",
    )
    artifact_packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    manifest_packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )

    assert artifact_packet["artifact_requirements_accepted"] == 1
    assert artifact_packet["artifact_requirements_missing"] == 6
    assert manifest_packet["artifact_requirements_accepted"] == 1
    assert manifest_packet["artifact_requirements_missing"] == 6
    assert manifest_packet["audit"]["metadata_manifest_files_read"] is True


def test_whatsapp_external_evidence_bundle_replays_through_benchmark_handoff_without_reading_artifacts() -> None:
    repo = InMemoryRepository()
    payload = whatsapp_status_webhook_payload()

    result = ingest_whatsapp_sandbox_webhook(
        repository=repo,
        client_id="demo",
        payload=payload,
        headers=build_whatsapp_signature_header(payload),
        webhook_app_secret="sandbox_app_secret",
        approval_by_provider_message_id={"wamid.sandbox.msg.0001": "approval_demo_1"},
    )
    bundle = build_whatsapp_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T11:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-2",
    )
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )

    assert packet["mode"] == "local_external_evidence_bundle_handoff_packet"
    assert packet["benchmark_parity"] is False
    assert packet["ship_ready"] is False
    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert packet["external_evidence_bundles"][0]["bundle_status"] == "accepted_for_external_handoff"
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False


@pytest.mark.parametrize(
    ("fixture_factory", "operation", "expected_endpoint"),
    [
        (gstn_gstr1_upload_response, "gstr1_return_upload", "gstn.gstr1.upload"),
        (gsp_gstr2b_pull_response, "gstr2b_pull", "gstn.gstr2b.pull"),
    ],
)
def test_gst_sandbox_fixtures_drive_local_contract_preparation(
    fixture_factory,
    operation: str,
    expected_endpoint: str,
) -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = fixture_factory()

    contract = prepare_gstn_api_exchange_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        operation=operation,
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
    )

    assert contract["status"] == "approval_required"
    assert contract["request"]["endpoint_key"] == expected_endpoint
    payload_digest = contract["request"]["payload_digest"]
    for key, expected_value in fixture["request_payload"].items():
        assert payload_digest[key] == expected_value
    if operation == "gstr1_return_upload":
        assert payload_digest["statutory_bundle"]["bundle_type"] == "gstr1_sales_tax_events"
        assert payload_digest["statutory_bundle"]["period"] == fixture["request_payload"]["period"]
    assert_local_contract_audit(
        contract["audit"],
        limitation=GSTN_API_CONTRACT_LIMITATION,
        requested_by="accountant",
        approval_required=True,
        gstn_api_called=False,
        nic_api_called=False,
        sandbox_credentials_used=False,
        statutory_filing_performed=False,
    )
    approval = assert_pending_approval(repo, "submit_gstn_api_request", expected_data={"mode": "local_contract_mock"})
    assert approval.data["request"]["request_id"] == contract["request"]["request_id"]


@pytest.mark.parametrize(
    ("provider", "fixture_factory", "expected_status", "manual_fallback_required"),
    [
        ("gstn_nic", gstn_gstr1_upload_response, "accepted", False),
        ("gstn_nic", gstn_validation_failed_response, "validation_failed", True),
        ("gsp_sandbox", gsp_manual_review_response, "needs_manual_review", True),
    ],
)
def test_gst_sandbox_response_fixtures_drive_local_response_normalization(
    provider: str,
    fixture_factory,
    expected_status: str,
    manual_fallback_required: bool,
) -> None:
    repo = InMemoryRepository()
    fixture = fixture_factory()
    request = {
        "request_id": "gstn_req_test_001",
        "operation": fixture["operation"],
        "endpoint_key": "gstn.gstr1.upload" if fixture["operation"] == "gstr1_return_upload" else "gstn.gstr2b.pull",
        "gstin": fixture["gstin"],
        "payload_digest": fixture["request_payload"],
    }

    result = normalize_gstn_api_response_contract(
        repository=repo,
        client_id="demo",
        provider=provider,
        request=request,
        response_payload=fixture,
    )

    assert result["status"] == expected_status
    assert result["provider"] == provider
    assert result["request"]["request_id"] == "gstn_req_test_001"
    assert result["response"]["portal_reference"] in {
        fixture["response"].get("reference_id"),
        fixture["response"].get("portal_reference"),
    }
    assert_local_contract_audit(
        result["audit"],
        limitation=GSTN_API_CONTRACT_LIMITATION,
        provider=provider,
        gstn_api_called=False,
        nic_api_called=False,
        gsp_api_called=False,
        sandbox_response_processed=True,
        manual_fallback_required=manual_fallback_required,
        statutory_filing_performed=False,
    )
    assert_last_action_log(repo, action_type="gstn_api_response_normalized", status=expected_status)


def test_gst_sandbox_adapter_fixture_reuses_existing_response_normalization_contract() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()
    request_contract = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )

    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload=fixture,
    )

    assert result["status"] == "accepted"
    assert result["adapter"]["connector"] == "gstn_sandbox"
    assert result["adapter"]["response_processed"] is True
    assert result["provider_request"]["path"] == "/sandbox/gstn/gstr1/upload"
    assert result["proof_transcript"]["proof_safe"] is True
    assert_last_action_log(repo, action_type="gstn_api_response_normalized", status="accepted")


def test_gst_proof_artifact_and_manifest_builders_match_proof_packet_contract() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()
    request_contract = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )
    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload=fixture,
    )
    artifact = build_gst_sandbox_proof_artifact_metadata(
        adapter_result=result,
        run_timestamp="2026-05-23T11:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-3",
    )
    manifest = build_gst_sandbox_proof_metadata_manifest(
        adapter_result=result,
        run_timestamp="2026-05-23T11:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-3",
    )
    artifact_packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    manifest_packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )

    assert artifact_packet["artifact_requirements_accepted"] == 1
    assert artifact_packet["artifact_requirements_missing"] == 6
    assert manifest_packet["artifact_requirements_accepted"] == 1
    assert manifest_packet["artifact_requirements_missing"] == 6
    assert manifest_packet["audit"]["metadata_manifest_files_read"] is True


def test_gst_external_evidence_bundle_replays_through_benchmark_handoff_without_reading_artifacts() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    fixture = gstn_gstr1_upload_response()
    request_contract = prepare_gst_sandbox_exchange(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        provider="gstn_nic",
        operation=fixture["operation"],
        gstin=fixture["gstin"],
        requested_by="accountant",
        payload=fixture["request_payload"],
        base_url="https://gstn-sandbox.example.test",
        sandbox_client_id="gstn_client_id",
        signing_secret="gstn_signing_secret",
    )
    result = ingest_gst_sandbox_response(
        repository=repo,
        client_id="demo",
        provider="gstn_nic",
        request_contract=request_contract,
        response_payload=fixture,
    )
    bundle = build_gst_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T11:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-3",
    )
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )

    assert packet["mode"] == "local_external_evidence_bundle_handoff_packet"
    assert packet["benchmark_parity"] is False
    assert packet["ship_ready"] is False
    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert packet["external_evidence_bundles"][0]["bundle_status"] == "accepted_for_external_handoff"
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False


def test_tally_fixtures_support_audit_only_sync_status_import() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_raj", amount=11800, status="open")],
        payments=[Payment(id="pay_1", customer_id="cust_raj", amount=11800, status="reconciled")],
    )
    status_payload = tally_status_payload_from_xml()
    rowset = tally_odbc_rows()

    result = import_accounting_sync_status(
        repository=repo,
        client_id="demo",
        system="tally",
        status_payload=status_payload,
    )

    assert result["status"] == "accepted"
    assert result["items"] == status_payload["items"]
    assert repo.get_invoices()[0].status == "open"
    assert repo.get_payments()[0].status == "reconciled"
    assert rowset["recordset"] == "voucher_summary"
    assert len(rowset["rows"]) == 2
    assert_local_contract_audit(
        result["audit"],
        limitation=LOCAL_SYNC_LIMITATION,
        external_write_performed=False,
        ledger_mutation_performed=False,
    )


def test_tally_xml_status_fixture_drives_bridge_normalization_without_ledger_mutation() -> None:
    repo = InMemoryRepository()

    result = normalize_accounting_bridge_payload(
        repository=repo,
        client_id="demo",
        system="tally",
        bridge_mode="xml_status_receipt",
        payload=tally_status_xml_text(),
    )

    assert result["status"] == "accepted"
    assert result["bridge_mode"] == "xml_status_receipt"
    assert result["items"][0]["record_type"] == "invoice"
    assert result["summary"] == {"records_total": 2, "accepted_records": 2, "manual_review_records": 0}
    assert_local_contract_audit(
        result["audit"],
        limitation=LOCAL_SYNC_LIMITATION,
        external_write_performed=False,
        ledger_mutation_performed=False,
        bridge_payload_processed=True,
        manual_fallback_required=False,
    )
    assert_last_action_log(repo, action_type="normalize_accounting_bridge_payload", status="accepted")


def test_tally_execution_harness_uses_proof_safe_transcript_for_xml_fixture() -> None:
    result = build_tally_bridge_execution_harness(
        system="tally",
        bridge_mode="xml_status_receipt",
        company_selection={"company_name": "Demo Traders Pvt Ltd", "company_id": "cmp_demo_1"},
        payload_reference="redacted://tally/sandbox/xml-status-1",
        configured_env_names={
            "TALLY_SANDBOX_BASE_URL",
            "TALLY_SANDBOX_COMPANY_NAME",
            "TALLY_SANDBOX_BRIDGE_MODE",
            "TALLY_SANDBOX_XML_GATEWAY_URL",
        },
    )

    assert result["status"] == "ready_for_local_execution_harness"
    assert result["proof_transcript"]["proof_safe"] is True
    assert result["proof_transcript"]["customer_data_redacted"] is True
    assert result["bridge_route"]["transport"] == "xml_gateway"


def test_tally_execution_harness_artifact_metadata_is_accepted_by_proof_collection_packet() -> None:
    harness = build_tally_bridge_execution_harness(
        system="tally",
        bridge_mode="xml_status_receipt",
        company_selection={"company_name": "Demo Traders Pvt Ltd", "company_id": "cmp_demo_1"},
        payload_reference="redacted://tally/sandbox/xml-status-1",
        configured_env_names={
            "TALLY_SANDBOX_BASE_URL",
            "TALLY_SANDBOX_COMPANY_NAME",
            "TALLY_SANDBOX_BRIDGE_MODE",
            "TALLY_SANDBOX_XML_GATEWAY_URL",
        },
    )
    artifact = build_tally_bridge_proof_artifact_metadata(
        execution_harness=harness,
        run_timestamp="2026-05-23T10:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    manifest = build_tally_bridge_proof_metadata_manifest(
        execution_harness=harness,
        run_timestamp="2026-05-23T10:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    manifest_packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )

    assert packet["artifact_requirements_accepted"] == 1
    assert packet["artifact_requirements_missing"] == 6
    assert packet["artifact_requirements_rejected"] == 0
    assert manifest["generated_from"] == "tally_sync_adapter"
    assert manifest_packet["artifact_requirements_accepted"] == 1
    assert manifest_packet["artifact_requirements_missing"] == 6
    assert manifest_packet["artifact_requirements_rejected"] == 0
    assert manifest_packet["audit"]["metadata_manifest_files_read"] is True


def test_tally_external_evidence_bundle_replays_through_benchmark_handoff_without_reading_artifacts() -> None:
    harness = build_tally_bridge_execution_harness(
        system="tally",
        bridge_mode="xml_status_receipt",
        company_selection={"company_name": "Demo Traders Pvt Ltd", "company_id": "cmp_demo_1"},
        payload_reference="redacted://tally/sandbox/xml-status-1",
        configured_env_names={
            "TALLY_SANDBOX_BASE_URL",
            "TALLY_SANDBOX_COMPANY_NAME",
            "TALLY_SANDBOX_BRIDGE_MODE",
            "TALLY_SANDBOX_XML_GATEWAY_URL",
        },
    )
    bundle = build_tally_bridge_external_evidence_bundle(
        execution_harness=harness,
        run_timestamp="2026-05-23T12:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-4",
    )
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )

    assert packet["mode"] == "local_external_evidence_bundle_handoff_packet"
    assert packet["benchmark_parity"] is False
    assert packet["ship_ready"] is False
    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert packet["external_evidence_bundles"][0]["bundle_status"] == "accepted_for_external_handoff"
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False


def test_tally_odbc_fixture_drives_manual_review_bridge_normalization() -> None:
    repo = InMemoryRepository()

    result = normalize_accounting_bridge_payload(
        repository=repo,
        client_id="demo",
        system="busy",
        bridge_mode="odbc_rowset",
        payload=tally_odbc_manual_review_rows(),
    )

    assert result["status"] == "needs_manual_review"
    assert result["bridge_mode"] == "odbc_rowset"
    assert result["items"][0]["record_type"] == "invoice"
    assert result["items"][1]["record_type"] == "payment"
    assert result["summary"] == {"records_total": 2, "accepted_records": 1, "manual_review_records": 1}
    assert_local_contract_audit(
        result["audit"],
        limitation=LOCAL_SYNC_LIMITATION,
        external_write_performed=False,
        ledger_mutation_performed=False,
        bridge_payload_processed=True,
        manual_fallback_required=True,
    )
    assert_last_action_log(repo, action_type="normalize_accounting_bridge_payload", status="needs_manual_review")


def test_payment_webhook_fixture_reconciles_locally_when_signature_fixture_is_verified() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    fixture = payment_webhook_event()

    result = ingest_payment_gateway_webhook_contract(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider=fixture["provider"],
        webhook_event=fixture,
    )

    assert result["status"] == "reconciled"
    assert result["payment"]["matched_invoice_id"] == "inv_1"
    assert repo.effective_invoice_projection(repo.get_invoices()[0])["status"] == "paid"
    assert repo.get_payments()[0].raw_source["gateway_event"]["payment_id"] == fixture["payment_id"]
    assert_local_contract_audit(
        result["audit"],
        limitation=LOCAL_PAYMENT_GATEWAY_LIMITATION,
        provider="razorpay",
        live_webhook_received=False,
        webhook_signature_verified=True,
        payment_gateway_api_called=False,
        bank_execution_performed=False,
        duplicate_event_ignored=False,
        payment_record_created=True,
    )


def test_payment_failed_webhook_fixture_does_not_mutate_invoice_or_create_payment() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    fixture = payment_failed_webhook_event()

    result = ingest_payment_gateway_webhook_contract(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider=fixture["provider"],
        webhook_event=fixture,
    )

    assert result["status"] == "ignored_non_success_event"
    assert result["payment"] is None
    assert repo.get_invoices()[0].status == "open"
    assert repo.get_payments() == []
    assert_local_contract_audit(
        result["audit"],
        limitation=LOCAL_PAYMENT_GATEWAY_LIMITATION,
        provider="razorpay",
        live_webhook_received=False,
        webhook_signature_verified=True,
        payment_gateway_api_called=False,
        bank_execution_performed=False,
        duplicate_event_ignored=False,
        payment_record_created=False,
    )
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="ignored_non_success_event")


def test_duplicate_payment_webhook_fixture_is_ignored_after_first_reconciliation() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    fixture = payment_webhook_event()

    first = ingest_payment_gateway_webhook_contract(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider=fixture["provider"],
        webhook_event=fixture,
    )
    duplicate = ingest_payment_gateway_webhook_contract(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider=fixture["provider"],
        webhook_event=fixture,
    )

    assert first["status"] == "reconciled"
    assert duplicate["status"] == "duplicate_ignored"
    assert len(repo.get_payments()) == 1
    assert duplicate["payment"]["payment_id"] == repo.get_payments()[0].id
    assert duplicate["payment"]["matched_invoice_id"] == "inv_1"
    assert_local_contract_audit(
        duplicate["audit"],
        limitation=LOCAL_PAYMENT_GATEWAY_LIMITATION,
        provider="razorpay",
        live_webhook_received=False,
        webhook_signature_verified=False,
        payment_gateway_api_called=False,
        bank_execution_performed=False,
        duplicate_event_ignored=True,
        payment_record_created=False,
    )
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="duplicate_ignored")


def test_cashfree_payment_webhook_fixture_reuses_local_payment_sandbox_adapter_contract() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = cashfree_success_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="cashfree",
        payload=payload,
        headers=build_cashfree_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "reconciled"
    assert result["adapter"]["provider"] == "cashfree"
    assert result["adapter"]["signature_verified"] is True
    assert result["payment"]["matched_invoice_id"] == "inv_1"
    assert result["provider_payload"]["payment_status"] == "success"
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="reconciled")


def test_phonepe_payment_webhook_fixture_reuses_local_payment_sandbox_adapter_contract() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = phonepe_success_webhook_payload()

    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="phonepe",
        payload=payload,
        headers=build_phonepe_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )

    assert result["status"] == "reconciled"
    assert result["adapter"]["provider"] == "phonepe"
    assert result["adapter"]["signature_verified"] is True
    assert result["payment"]["matched_invoice_id"] == "inv_1"
    assert result["provider_payload"]["payment_status"] == "completed"
    assert_last_action_log(repo, action_type="payment_gateway_webhook_contract", status="reconciled")


def test_payment_gateway_proof_artifact_builder_matches_proof_packet_contract() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()
    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )
    artifact = build_payment_gateway_sandbox_proof_artifact_metadata(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])

    assert packet["artifact_requirements_accepted"] == 1
    assert packet["artifact_requirements_missing"] == 6
    assert packet["artifact_requirements_rejected"] == 0


def test_payment_gateway_proof_manifest_builder_matches_proof_packet_contract() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()
    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )
    manifest = build_payment_gateway_sandbox_proof_metadata_manifest(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )

    assert packet["artifact_requirements_accepted"] == 1
    assert packet["artifact_requirements_missing"] == 6
    assert packet["artifact_requirements_rejected"] == 0
    assert packet["audit"]["metadata_manifest_files_read"] is True


def test_payment_gateway_external_evidence_bundle_replays_through_benchmark_handoff_without_reading_artifacts() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=11800, status="open")]
    )
    payload = razorpay_captured_webhook_payload()
    result = ingest_payment_gateway_sandbox_payload(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        provider="razorpay",
        payload=payload,
        headers=build_razorpay_signature_header(payload),
        webhook_signing_secret="sandbox_signature_key",
    )
    bundle = build_payment_gateway_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )

    assert packet["mode"] == "local_external_evidence_bundle_handoff_packet"
    assert packet["benchmark_parity"] is False
    assert packet["ship_ready"] is False
    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert packet["external_evidence_bundles"][0]["bundle_status"] == "accepted_for_external_handoff"
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False


def test_proof_artifact_manifest_fixture_is_accepted_without_artifact_reads() -> None:
    manifest = proof_artifact_manifest()
    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    requirements = {entry["artifact_id"]: entry for entry in packet["artifact_requirements"]}

    assert packet["status"] == "missing_external_evidence"
    assert packet["artifact_requirements_accepted"] == 2
    assert packet["artifact_requirements_missing"] == 5
    assert packet["artifact_requirements_rejected"] == 0
    assert requirements["provider_sandbox_adapter_evidence"]["status"] == "metadata_accepted_for_review"
    assert requirements["owner_briefing_delivery_evidence"]["status"] == "metadata_accepted_for_review"
    assert packet["audit"]["metadata_manifest_files_read"] is True
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False
