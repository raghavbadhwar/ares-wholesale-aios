from __future__ import annotations

import pytest

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.gstn_sandbox import (
    build_gst_sandbox_external_evidence_bundle,
    build_gst_sandbox_proof_artifact_metadata,
    build_gst_sandbox_proof_metadata_manifest,
    ingest_gst_sandbox_response,
    prepare_gst_sandbox_exchange,
)
from apps.ares.ares.connectors.payment_gateway_sandbox import (
    build_payment_gateway_sandbox_external_evidence_bundle,
    build_payment_gateway_sandbox_proof_artifact_metadata,
    build_payment_gateway_sandbox_proof_metadata_manifest,
    ingest_payment_gateway_sandbox_payload,
)
from apps.ares.ares.connectors.proof_handoff import (
    build_external_evidence_bundle,
    build_proof_metadata_manifest,
    build_provider_sandbox_proof_artifact_metadata,
)
from apps.ares.ares.connectors.tally_sync_adapter import (
    build_tally_bridge_execution_harness,
    build_tally_bridge_external_evidence_bundle,
    build_tally_bridge_proof_artifact_metadata,
    build_tally_bridge_proof_metadata_manifest,
)
from apps.ares.ares.connectors.whatsapp_sandbox import (
    build_whatsapp_sandbox_external_evidence_bundle,
    build_whatsapp_sandbox_proof_artifact_metadata,
    build_whatsapp_sandbox_proof_metadata_manifest,
    ingest_whatsapp_sandbox_webhook,
)
from apps.ares.ares.data.models import Invoice
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.connectors.proof_packets import (
    build_benchmark_external_evidence_bundle_packet,
    build_benchmark_proof_collection_packet,
)
from tests.ares.support import (
    assert_redaction_safe_payload,
    build_razorpay_signature_header,
    build_whatsapp_signature_header,
    gst_sandbox_external_evidence_bundle,
    gst_sandbox_proof_artifact,
    gst_sandbox_proof_manifest,
    gstn_gstr1_upload_response,
    payment_gateway_sandbox_external_evidence_bundle,
    payment_gateway_sandbox_proof_artifact,
    payment_gateway_sandbox_proof_manifest,
    razorpay_captured_webhook_payload,
    tally_sandbox_external_evidence_bundle,
    tally_sandbox_proof_artifact,
    tally_sandbox_proof_manifest,
    whatsapp_sandbox_external_evidence_bundle,
    whatsapp_sandbox_proof_artifact,
    whatsapp_sandbox_proof_manifest,
    whatsapp_status_webhook_payload,
)


def test_shared_proof_handoff_helpers_build_benchmark_accepted_metadata() -> None:
    artifact = build_provider_sandbox_proof_artifact_metadata(
        provider="gstn_nic",
        transcript_id="gst_txn_demo_1",
        run_timestamp="2026-05-23T12:30:00+05:30",
        reviewer_reference="redacted-reviewer-1",
        artifact_reference_prefix="redacted://gst_sandbox/gstn_nic",
    )
    manifest = build_proof_metadata_manifest(artifact=artifact, generated_from="gstn_sandbox")
    bundle = build_external_evidence_bundle(
        artifact=artifact,
        transcript_id="gst_txn_demo_1",
        run_timestamp="2026-05-23T12:30:00+05:30",
        reviewer_reference="redacted-reviewer-1",
        bundle_prefix="external-evidence-bundle-gst",
        envelope_prefix="signed-gst-proof",
        snapshot_prefix="registry-snapshot-gst",
    )
    repeated_bundle = build_external_evidence_bundle(
        artifact=artifact,
        transcript_id="gst_txn_demo_1",
        run_timestamp="2026-05-23T12:30:00+05:30",
        reviewer_reference="redacted-reviewer-1",
        bundle_prefix="external-evidence-bundle-gst",
        envelope_prefix="signed-gst-proof",
        snapshot_prefix="registry-snapshot-gst",
    )

    artifact_packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    manifest_packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    assert artifact["artifact_path_or_reference"] == "redacted://gst_sandbox/gstn_nic/gst_txn_demo_1"
    assert manifest["generated_from"] == "gstn_sandbox"
    assert bundle == repeated_bundle
    assert bundle["bundle_id"].startswith("external-evidence-bundle-gst-")
    assert bundle["signed_envelopes"][0]["envelope_id"].startswith("signed-gst-proof-")
    assert artifact_packet["artifact_requirements_accepted"] == 1
    assert manifest_packet["audit"]["metadata_manifest_files_read"] is True
    assert bundle["review_decisions"][0]["decision"] == "approved"


def test_shared_proof_handoff_helpers_preserve_explicit_artifact_reference_override() -> None:
    artifact = build_provider_sandbox_proof_artifact_metadata(
        provider="whatsapp_business",
        transcript_id="whatsapp_txn_demo_1",
        run_timestamp="2026-05-23T13:00:00+05:30",
        reviewer_reference="redacted-reviewer-2",
        artifact_reference_prefix="redacted://whatsapp_business",
        artifact_path_or_reference="redacted://custom/whatsapp-proof-1.json",
    )

    assert artifact["artifact_path_or_reference"] == "redacted://custom/whatsapp-proof-1.json"
    assert artifact["provider"] == "whatsapp_business"
    assert artifact["redaction_confirmed"] is True


def _build_payment_fixture_triplet() -> tuple[dict, dict, dict]:
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
    manifest = build_payment_gateway_sandbox_proof_metadata_manifest(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    bundle = build_payment_gateway_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T10:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
        bundle_token_override="demo",
    )
    return artifact, manifest, bundle


def _build_whatsapp_fixture_triplet() -> tuple[dict, dict, dict]:
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
    bundle = build_whatsapp_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T11:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-2",
        bundle_token_override="demo",
    )
    return artifact, manifest, bundle


def _build_gst_fixture_triplet() -> tuple[dict, dict, dict]:
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
    bundle = build_gst_sandbox_external_evidence_bundle(
        adapter_result=result,
        run_timestamp="2026-05-23T11:30:00+05:30",
        reviewer_reference="redacted-ops-reviewer-3",
        bundle_token_override="demo",
    )
    return artifact, manifest, bundle


def _build_tally_fixture_triplet() -> tuple[dict, dict, dict]:
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
        run_timestamp="2026-05-23T12:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-4",
    )
    manifest = build_tally_bridge_proof_metadata_manifest(
        execution_harness=harness,
        run_timestamp="2026-05-23T12:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-4",
    )
    bundle = build_tally_bridge_external_evidence_bundle(
        execution_harness=harness,
        run_timestamp="2026-05-23T12:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-4",
        bundle_token_override="demo",
    )
    return artifact, manifest, bundle


@pytest.mark.parametrize(
    ("label", "builder", "artifact_fixture", "manifest_fixture", "bundle_fixture"),
    [
        (
            "payment_gateway",
            _build_payment_fixture_triplet,
            payment_gateway_sandbox_proof_artifact,
            payment_gateway_sandbox_proof_manifest,
            payment_gateway_sandbox_external_evidence_bundle,
        ),
        (
            "whatsapp",
            _build_whatsapp_fixture_triplet,
            whatsapp_sandbox_proof_artifact,
            whatsapp_sandbox_proof_manifest,
            whatsapp_sandbox_external_evidence_bundle,
        ),
        (
            "gst",
            _build_gst_fixture_triplet,
            gst_sandbox_proof_artifact,
            gst_sandbox_proof_manifest,
            gst_sandbox_external_evidence_bundle,
        ),
        (
            "tally",
            _build_tally_fixture_triplet,
            tally_sandbox_proof_artifact,
            tally_sandbox_proof_manifest,
            tally_sandbox_external_evidence_bundle,
        ),
    ],
)
def test_shared_proof_handoff_outputs_match_committed_redacted_provider_fixtures(
    label: str,
    builder,
    artifact_fixture,
    manifest_fixture,
    bundle_fixture,
) -> None:
    artifact, manifest, bundle = builder()
    expected_artifact = artifact_fixture()
    expected_manifest = manifest_fixture()
    expected_bundle = bundle_fixture()

    assert_redaction_safe_payload(expected_artifact)
    assert_redaction_safe_payload(expected_manifest)
    assert_redaction_safe_payload(expected_bundle)
    assert artifact == expected_artifact, label
    assert manifest == expected_manifest, label
    assert bundle == expected_bundle, label

    manifest_packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    bundle_packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result=f"{label} fixture parity passed",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )

    assert manifest_packet["artifact_requirements_accepted"] == 1
    assert bundle_packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
