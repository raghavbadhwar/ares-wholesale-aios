from __future__ import annotations

from datetime import datetime

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.whatsapp_sandbox import (
    WHATSAPP_SANDBOX_ADAPTER_LIMITATION,
    WHATSAPP_SANDBOX_HEALTHCHECK_LIMITATION,
    WHATSAPP_SANDBOX_PROOF_LIMITATION,
    build_whatsapp_sandbox_external_evidence_bundle,
    build_whatsapp_sandbox_healthcheck,
    build_whatsapp_sandbox_proof_artifact_metadata,
    build_whatsapp_sandbox_proof_metadata_manifest,
    build_whatsapp_sandbox_reviewed_evidence_intake,
    ingest_whatsapp_sandbox_webhook,
    prepare_whatsapp_sandbox_template_payload,
)
from apps.ares.ares.data.models import Customer
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.connectors.proof_packets import (
    build_benchmark_external_evidence_bundle_packet,
    build_benchmark_proof_collection_packet,
    build_benchmark_reviewed_evidence_intake_packet,
)
from apps.ares.ares.workflows.whatsapp_business import prepare_whatsapp_business_message
from tests.ares.support import (
    assert_local_contract_audit,
    build_whatsapp_signature_header,
    whatsapp_sandbox_external_evidence_bundle,
    whatsapp_sandbox_reviewed_evidence_intake,
    whatsapp_inbound_message_payload,
    whatsapp_sandbox_proof_artifact,
    whatsapp_sandbox_proof_manifest,
    whatsapp_status_webhook_payload,
)


def test_should_prepare_meta_style_template_payload_from_whatsapp_approval_contract() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Ramesh Stores", phone="+919999999999", preferred_language="marathi")]
    )
    approvals = ApprovalService(repo)
    draft = prepare_whatsapp_business_message(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        template_name="payment_reminder",
        body="नमस्कार, तुमची उधारी रक्कम बाकी आहे.",
        requested_by="owner",
        dedupe_key="waba:payment:inv_1",
    )
    approval = repo.find_approval(draft["approval_id"])
    assert approval is not None

    result = prepare_whatsapp_sandbox_template_payload(
        approval_data={**approval.data, "approval_id": approval.id},
        phone_number_id="meta_sandbox_phone_001",
        business_account_id="waba_sandbox_001",
    )

    assert result["status"] == "payload_prepared"
    assert result["request"]["phone_number_id"] == "meta_sandbox_phone_001"
    assert result["request"]["business_account_id"] == "waba_sandbox_001"
    assert result["request"]["payload"]["to"] == "+919999999999"
    assert result["request"]["payload"]["template"]["name"] == "payment_reminder"
    assert result["request"]["payload"]["template"]["language"]["code"] == "mr"
    assert result["request"]["payload"]["template"]["components"][0]["parameters"][0]["text"] == "नमस्कार, तुमची उधारी रक्कम बाकी आहे."
    assert_local_contract_audit(
        result["audit"],
        limitation=WHATSAPP_SANDBOX_ADAPTER_LIMITATION,
        external_whatsapp_business_api_called=False,
        template_send_performed=False,
        webhook_signature_verified=False,
    )


def test_should_verify_inbound_whatsapp_webhook_and_return_parser_events() -> None:
    repo = InMemoryRepository()
    payload = whatsapp_inbound_message_payload()

    result = ingest_whatsapp_sandbox_webhook(
        repository=repo,
        client_id="demo",
        payload=payload,
        headers=build_whatsapp_signature_header(payload),
        webhook_app_secret="sandbox_app_secret",
        received_at=datetime(2026, 5, 23, 9, 30),
    )

    assert result["status"] == "parsed"
    assert len(result["messages"]) == 1
    assert result["delivery_updates"] == []
    assert result["delivery_receipts"] == []
    assert result["messages"][0].source == "whatsapp_sandbox"
    assert result["audit"]["webhook_signature_verified"] is True
    assert result["adapter"]["signature_verified"] is True
    assert result["adapter"]["delivery_sink_invoked"] is False
    assert result["proof_transcript"]["proof_safe"] is True
    assert result["proof_transcript"]["signature_verified"] is True
    assert result["proof_transcript"]["limitation"] == WHATSAPP_SANDBOX_PROOF_LIMITATION


def test_should_verify_status_webhook_and_write_delivery_receipt_audit_log() -> None:
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
    assert result["messages"] == []
    assert len(result["delivery_updates"]) == 1
    assert len(result["delivery_receipts"]) == 1
    assert result["delivery_receipts"][0]["delivery_status"] == "delivered"
    assert result["adapter"]["delivery_sink_invoked"] is True
    assert repo.list_action_logs()[-1].action_type == "whatsapp_delivery_receipt"
    assert repo.list_action_logs()[-1].approval_id == "approval_demo_1"


def test_should_block_unsigned_whatsapp_webhook_without_processing_payload() -> None:
    repo = InMemoryRepository()
    payload = whatsapp_inbound_message_payload()

    result = ingest_whatsapp_sandbox_webhook(
        repository=repo,
        client_id="demo",
        payload=payload,
        headers={"X-Hub-Signature-256": "sha256=mismatch"},
        webhook_app_secret="sandbox_app_secret",
    )

    assert result["status"] == "blocked_unverified_signature"
    assert result["messages"] == []
    assert result["delivery_updates"] == []
    assert result["delivery_receipts"] == []
    assert result["adapter"]["signature_verified"] is False
    assert repo.list_action_logs() == []


def test_should_expose_whatsapp_sandbox_healthcheck_gate() -> None:
    blocked = build_whatsapp_sandbox_healthcheck()
    ready = build_whatsapp_sandbox_healthcheck(
        configured_env_names={
            "META_WABA_SANDBOX_PHONE_NUMBER_ID",
            "META_WABA_SANDBOX_ACCESS_TOKEN",
            "META_WABA_SANDBOX_VERIFY_TOKEN",
            "META_WABA_SANDBOX_APP_SECRET",
            "META_WABA_SANDBOX_BUSINESS_ACCOUNT_ID",
        },
        safe_test_environment_confirmed=True,
    )

    assert blocked["status"] == "blocked"
    assert blocked["can_run_local_adapter_tests"] is False
    assert "META_WABA_SANDBOX_APP_SECRET" in blocked["missing_env_names"]
    assert blocked["audit"]["limitation"] == WHATSAPP_SANDBOX_HEALTHCHECK_LIMITATION

    assert ready["status"] == "ready_for_local_adapter_tests"
    assert ready["can_run_local_adapter_tests"] is True
    assert ready["fixture_families"] == [
        "inbound message webhook payload",
        "delivery status webhook payload",
        "template payload shaping contract",
    ]
    assert ready["webhook_signature_scheme"] == "hmac_sha256"
    assert ready["missing_env_names"] == []


def test_should_build_proof_safe_whatsapp_artifact_metadata_accepted_by_proof_packet() -> None:
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
    packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert artifact["provider"] == "whatsapp_business"
    assert artifact["redaction_confirmed"] is True
    assert artifact["artifact_path_or_reference"].startswith("redacted://whatsapp_business/whatsapp_txn_")
    assert requirement["status"] == "metadata_accepted_for_review"


def test_should_build_whatsapp_proof_metadata_manifest_for_operator_handoff() -> None:
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

    manifest = build_whatsapp_sandbox_proof_metadata_manifest(
        adapter_result=result,
        run_timestamp="2026-05-23T11:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-2",
    )
    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert manifest["generated_from"] == "whatsapp_sandbox"
    assert manifest["redaction_confirmed"] is True
    assert len(manifest["artifacts"]) == 1
    assert manifest["artifacts"][0]["provider"] == "whatsapp_business"
    assert requirement["status"] == "metadata_accepted_for_review"
    assert packet["audit"]["metadata_manifest_files_read"] is True


def test_whatsapp_proof_artifact_and_manifest_fixtures_are_accepted_by_proof_packet() -> None:
    artifact = whatsapp_sandbox_proof_artifact()
    manifest = whatsapp_sandbox_proof_manifest()
    artifact_packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    manifest_packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )

    assert {item["artifact_id"]: item for item in artifact_packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]["status"] == "metadata_accepted_for_review"
    assert {item["artifact_id"]: item for item in manifest_packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]["status"] == "metadata_accepted_for_review"
    assert manifest_packet["audit"]["metadata_manifest_files_read"] is True


def test_should_build_whatsapp_external_evidence_bundle_for_operator_handoff() -> None:
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
    bundle_item = packet["external_evidence_bundles"][0]

    assert bundle["bundle_id"].startswith("external-evidence-bundle-whatsapp-")
    assert bundle["redaction_confirmed"] is True
    assert len(bundle["artifacts"]) == 1
    assert len(bundle["review_decisions"]) == 1
    assert len(bundle["signed_envelopes"]) == 1
    assert len(bundle["reviewer_key_registry_snapshots"]) == 1
    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert bundle_item["bundle_status"] == "accepted_for_external_handoff"
    assert bundle_item["proof_collection_summary"]["artifact_requirements_accepted"] == 1
    assert bundle_item["review_decision_summary"]["review_decisions_accepted"] == 1
    assert bundle_item["signed_envelope_summary"]["signed_envelopes_accepted"] == 1
    assert bundle_item["reviewer_key_registry_snapshot_summary"]["registry_snapshots_verified"] == 1
    assert packet["audit"]["external_evidence_bundle_files_read"] is True


def test_whatsapp_external_evidence_bundle_fixture_is_accepted_for_handoff() -> None:
    bundle = whatsapp_sandbox_external_evidence_bundle()
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    bundle_item = packet["external_evidence_bundles"][0]

    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert bundle_item["bundle_status"] == "accepted_for_external_handoff"
    assert bundle_item["review_decision_summary"]["review_decisions_accepted"] == 1
    assert bundle_item["signed_envelope_summary"]["signed_envelopes_accepted"] == 1
    assert bundle_item["reviewer_key_registry_snapshot_summary"]["registry_snapshots_verified"] == 1


def test_should_build_whatsapp_reviewed_evidence_intake_for_local_replay() -> None:
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

    intake = build_whatsapp_sandbox_reviewed_evidence_intake(
        adapter_result=result,
        external_evidence_bundle=bundle,
        reviewed_at="2026-05-23T11:40:00+05:30",
        reviewer_reference="redacted-whatsapp-reviewer-1",
    )
    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert intake["provider"] == "whatsapp_business"
    assert intake["subject_metadata_kind"] == "whatsapp_message_identity"
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["subject_metadata_summary"]["subject_scope"] == "whatsapp_template_delivery_review"
    assert item["subject_metadata_summary"]["metadata_ready"] is True


def test_whatsapp_reviewed_evidence_intake_fixture_is_accepted_by_packet() -> None:
    intake = whatsapp_sandbox_reviewed_evidence_intake()
    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"]["intakes_accepted_for_local_replay"] == 1
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["operator_login_summary"]["session_reference_present"] is True
    assert item["subject_metadata_summary"]["portal_reference_present"] is True


def test_whatsapp_reviewed_evidence_intake_blocks_on_missing_login_reference_and_subject_identifier() -> None:
    intake = whatsapp_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["login_reference"] = ""
    intake["subject_metadata"]["subject_reference"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"]["intakes_blocked"] == 1
    assert item["intake_status"] == "blocked_until_metadata_ready"
    assert item["operator_login_summary"]["metadata_ready"] is False
    assert item["subject_metadata_summary"]["metadata_ready"] is False
    assert item["rejection_reasons"] == [
        "operator_login_metadata.missing_field:login_reference",
        "subject_metadata.missing_identifier",
    ]


def test_whatsapp_reviewed_evidence_intake_blocks_after_reviewer_rejection_with_valid_metadata() -> None:
    intake = whatsapp_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_rejected"
    intake["review_rejection_reference"] = "redacted-whatsapp-review-rejection-1"
    intake["review_rejection_reasons"] = ["template_reference_mismatch"]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"]["intakes_rejected_after_review"] == 1
    assert item["intake_status"] == "blocked_after_review_rejection"
    assert item["operator_login_summary"]["metadata_ready"] is True
    assert item["subject_metadata_summary"]["metadata_ready"] is True
    assert item["review_rejection_summary"] == {
        "rejected_after_review": True,
        "review_rejection_reference_present": True,
        "review_rejection_reason_count": 1,
        "reopened_after_review_rejection": False,
        "review_resubmission_reference_present": False,
    }
    assert item["rejection_reasons"] == [
        "review_rejection_reason:template_reference_mismatch",
    ]


def test_whatsapp_reviewed_evidence_intake_reopens_after_corrected_resubmission() -> None:
    intake = whatsapp_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-whatsapp-review-rejection-1"
    intake["review_rejection_reasons"] = ["template_reference_mismatch"]
    intake["review_resubmission_reference"] = "redacted-whatsapp-review-resubmission-1"

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"][
        "intakes_resubmitted_after_review_rejection"
    ] == 1
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["operator_login_summary"]["metadata_ready"] is True
    assert item["subject_metadata_summary"]["metadata_ready"] is True
    assert item["review_rejection_summary"] == {
        "rejected_after_review": False,
        "review_rejection_reference_present": True,
        "review_rejection_reason_count": 1,
        "reopened_after_review_rejection": True,
        "review_resubmission_reference_present": True,
    }
    assert item["rejection_reasons"] == [
        "review_rejection_reason:template_reference_mismatch",
    ]


def test_whatsapp_reviewed_evidence_intake_blocks_on_mixed_valid_and_invalid_prior_review_history() -> None:
    intake = whatsapp_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-whatsapp-review-rejection-3"
    intake["review_rejection_reasons"] = ["template_approval_still_not_linked"]
    intake["review_resubmission_reference"] = "redacted-whatsapp-review-resubmission-3"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-whatsapp-review-rejection-1",
            "review_rejection_reasons": ["template_reference_mismatch"],
            "review_resubmission_reference": "redacted-whatsapp-review-resubmission-1",
        },
        {
            "review_rejection_reference": "redacted-whatsapp-review-rejection-2",
            "review_rejection_reasons": ["message_window_not_documented"],
            "review_resubmission_reference": "",
        },
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert packet["reviewed_evidence_intake_summary"][
        "intakes_with_multi_attempt_review_history"
    ] == 1
    assert item["intake_status"] == "blocked_until_metadata_ready"
    assert item["operator_login_summary"]["metadata_ready"] is True
    assert item["subject_metadata_summary"]["metadata_ready"] is True
    assert item["review_cycle_history_summary"] == {
        "prior_review_cycle_count": 2,
        "total_review_cycle_count": 3,
        "all_prior_cycles_complete": False,
        "multi_attempt_review_replay": True,
    }
    assert item["review_rejection_summary"] == {
        "rejected_after_review": False,
        "review_rejection_reference_present": True,
        "review_rejection_reason_count": 1,
        "reopened_after_review_rejection": True,
        "review_resubmission_reference_present": True,
    }
    assert item["rejection_reasons"] == [
        "prior_review_cycle:1:review_resubmission_reference_missing",
        "review_rejection_reason:template_approval_still_not_linked",
    ]
