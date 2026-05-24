from __future__ import annotations

from apps.ares.ares.connectors.proof_handoff import build_reviewer_key_registry_snapshot
from apps.ares.ares.connectors.proof_packets import (
    build_benchmark_external_evidence_bundle_packet,
    build_benchmark_proof_collection_packet,
    build_benchmark_proof_review_decision_ledger_packet,
    build_benchmark_proof_review_decision_packet,
    build_benchmark_proof_review_handoff_packet,
    build_benchmark_reviewed_evidence_intake_packet,
    build_benchmark_proof_review_signed_envelope_packet,
    build_benchmark_proof_reviewer_assignment_packet,
)
from tests.ares.support import (
    assert_redaction_safe_payload,
    external_evidence_bundle_blocked_packet_snapshot,
    external_evidence_bundle_combined_rejection_snapshot,
    external_evidence_bundle_mixed_snapshot_chain_snapshot,
    external_evidence_bundle_packet_snapshot,
    external_evidence_bundle_rejected_packet_snapshot,
    external_evidence_bundle_unverified_snapshot_chain_snapshot,
    gst_reviewed_evidence_intake_blocked_packet_snapshot,
    gst_sandbox_reviewed_evidence_intake,
    payment_gateway_sandbox_external_evidence_bundle,
    payment_gateway_sandbox_reviewed_evidence_intake,
    payment_reviewed_evidence_intake_blocked_packet_snapshot,
    proof_artifact_manifest,
    proof_collection_packet_snapshot,
    proof_review_decision_ledger_packet_snapshot,
    proof_review_decision_packet_snapshot,
    proof_review_handoff_packet_snapshot,
    proof_review_signed_envelope_blocked_packet_snapshot,
    proof_review_signed_envelope_combined_failure_snapshot,
    proof_review_signed_envelope_invalid_decision_snapshot,
    proof_review_signed_envelope_key_rejections_snapshot,
    proof_review_signed_envelope_mixed_snapshot_chain_snapshot,
    proof_review_signed_envelope_multi_snapshot_chain_snapshot,
    proof_review_signed_envelope_packet_snapshot,
    proof_reviewer_assignment_packet_snapshot,
    rejected_proof_collection_packet_snapshot,
    reviewed_evidence_intake_blocked_packet_snapshot,
    reviewed_evidence_intake_invalid_resubmission_packet_snapshot,
    reviewed_evidence_intake_mixed_packet_snapshot,
    reviewed_evidence_intake_mixed_rejection_cycle_packet_snapshot,
    reviewed_evidence_intake_packet_snapshot,
    reviewed_evidence_intake_long_chain_rejection_packet_snapshot,
    reviewed_evidence_intake_long_chain_resubmission_packet_snapshot,
    reviewed_evidence_intake_mixed_history_invalid_packet_snapshot,
    reviewed_evidence_intake_mixed_type_history_packet_snapshot,
    reviewed_evidence_intake_multi_attempt_rejection_packet_snapshot,
    reviewed_evidence_intake_multi_attempt_resubmission_packet_snapshot,
    reviewed_evidence_intake_multi_invalid_history_packet_snapshot,
    reviewed_evidence_intake_repeated_rejection_packet_snapshot,
    reviewed_evidence_intake_mixed_reopened_packet_snapshot,
    reviewed_evidence_intake_rejected_packet_snapshot,
    reviewed_evidence_intake_reopened_packet_snapshot,
    tally_reviewed_evidence_intake_blocked_packet_snapshot,
    tally_sandbox_reviewed_evidence_intake,
    whatsapp_reviewed_evidence_intake_blocked_packet_snapshot,
    whatsapp_sandbox_reviewed_evidence_intake,
)

_ALLOWED_AUDIT_KEY_PATHS = {"root.audit.secret_values_inspected"}
_LATEST_LOCAL_TEST_RESULT = "202 passed in 2.74s"


def _handoff_snapshot_projection(packet: dict) -> dict:
    return {
        "mode": packet["mode"],
        "review_scope": packet["review_scope"],
        "latest_local_test_result": packet["latest_local_test_result"],
        "artifact_review_summary": packet["artifact_review_summary"],
        "done_state_gate_review_summary": packet["done_state_gate_review_summary"],
        "artifact_review_statuses": {
            item["artifact_id"]: {
                "metadata_status": item["metadata_status"],
                "review_status": item["review_status"],
                "required_reviewer": item["required_reviewer"],
            }
            for item in packet["artifact_review_queue"]
        },
        "done_state_gate_review_statuses": {
            item["gate"]: {
                "metadata_status": item["metadata_status"],
                "review_status": item["review_status"],
                "accepted_artifact_ids": item["accepted_artifact_ids"],
                "missing_artifact_ids": item["missing_artifact_ids"],
                "rejected_artifact_ids": item["rejected_artifact_ids"],
            }
            for item in packet["done_state_gate_review_queue"]
        },
    }


def _decision_snapshot_projection(packet: dict) -> dict:
    return {
        "mode": packet["mode"],
        "decision_scope": packet["decision_scope"],
        "latest_local_test_result": packet["latest_local_test_result"],
        "artifact_review_decision_summary": packet["artifact_review_decision_summary"],
        "done_state_gate_review_decision_summary": packet["done_state_gate_review_decision_summary"],
        "artifact_review_decision_statuses": {
            item["artifact_id"]: {
                "decision_status": item["decision_status"],
                "decision": item["decision"],
                "reviewer": item["reviewer"],
                "rejection_reasons": item["rejection_reasons"],
            }
            for item in packet["artifact_review_decisions"]
        },
        "done_state_gate_review_decision_statuses": {
            item["gate"]: {
                "review_decision_status": item["review_decision_status"],
                "approved_artifact_ids": item["approved_artifact_ids"],
                "rejected_artifact_ids": item["rejected_artifact_ids"],
                "missing_review_decision_artifact_ids": item["missing_review_decision_artifact_ids"],
            }
            for item in packet["done_state_gate_review_decisions"]
        },
    }


def _assignment_snapshot_projection(packet: dict) -> dict:
    return {
        "mode": packet["mode"],
        "assignment_scope": packet["assignment_scope"],
        "latest_local_test_result": packet["latest_local_test_result"],
        "reviewer_assignment_summary": packet["reviewer_assignment_summary"],
        "reviewer_assignments": {
            item["artifact_id"]: {
                "assignment_status": item["assignment_status"],
                "reviewer_role": item["reviewer_role"],
                "specialized_subagent_profile": item["specialized_subagent_profile"],
                "blocked_reason": item["blocked_reason"],
            }
            for item in packet["reviewer_assignments"]
        },
    }


def _ledger_snapshot_projection(packet: dict) -> dict:
    return {
        "mode": packet["mode"],
        "ledger_scope": packet["ledger_scope"],
        "latest_local_test_result": packet["latest_local_test_result"],
        "review_decision_ledger_summary": packet["review_decision_ledger_summary"],
        "review_decision_ledger_statuses": {
            item["ledger_entry_id"]: {
                "replay_status": item["replay_status"],
                "artifact_id": item["artifact_id"],
                "decision_status": item["decision_status"],
                "rejection_reasons": item["rejection_reasons"],
            }
            for item in packet["review_decision_ledger_entries"]
        },
    }


def _signed_envelope_snapshot_projection(packet: dict) -> dict:
    return {
        "mode": packet["mode"],
        "signature_scope": packet["signature_scope"],
        "latest_local_test_result": packet["latest_local_test_result"],
        "signed_envelope_summary": packet["signed_envelope_summary"],
        "reviewer_key_registry_summary": packet["reviewer_key_registry_summary"],
        "reviewer_key_registry_snapshot_summary": packet[
            "reviewer_key_registry_snapshot_summary"
        ],
        "signed_review_envelopes": {
            item["envelope_id"]: {
                "signature_status": item["signature_status"],
                "artifact_id": item["artifact_id"],
                "decision_status": item["decision_status"],
                "reviewer": item["reviewer"],
                "key_registry_status": item.get("key_registry_status", ""),
                "key_registry_snapshot_id": item.get("key_registry_snapshot_id", ""),
                "key_registry_snapshot_hash": item.get("key_registry_snapshot_hash", ""),
                "rejection_reasons": item["rejection_reasons"],
            }
            for item in packet["signed_review_envelopes"]
        },
    }


def _reviewed_evidence_intake_snapshot_projection(packet: dict) -> dict:
    return {
        "mode": packet["mode"],
        "latest_local_test_result": packet["latest_local_test_result"],
        "reviewed_evidence_intake_summary": {
            "intakes_total": packet["reviewed_evidence_intake_summary"]["intakes_total"],
            "intakes_accepted_for_local_replay": packet["reviewed_evidence_intake_summary"][
                "intakes_accepted_for_local_replay"
            ],
            "intakes_blocked": packet["reviewed_evidence_intake_summary"]["intakes_blocked"],
            "intakes_blocked_until_metadata_ready": packet[
                "reviewed_evidence_intake_summary"
            ]["intakes_blocked_until_metadata_ready"],
            "intakes_rejected_after_review": packet["reviewed_evidence_intake_summary"][
                "intakes_rejected_after_review"
            ],
            "intakes_resubmitted_after_review_rejection": packet[
                "reviewed_evidence_intake_summary"
            ]["intakes_resubmitted_after_review_rejection"],
            "intakes_with_operator_login_metadata": packet[
                "reviewed_evidence_intake_summary"
            ]["intakes_with_operator_login_metadata"],
            "intakes_with_subject_metadata": packet["reviewed_evidence_intake_summary"][
                "intakes_with_subject_metadata"
            ],
        },
        "reviewed_evidence_intakes": {
            item["intake_id"]: {
                "bundle_id": item["bundle_id"],
                "artifact_id": item["artifact_id"],
                "provider": item["provider"],
                "intake_status": item["intake_status"],
                "review_outcome": item["review_outcome"],
                "operator_login_summary": item["operator_login_summary"],
                "subject_metadata_summary": item["subject_metadata_summary"],
                "review_rejection_summary": item["review_rejection_summary"],
                "rejection_reasons": item["rejection_reasons"],
            }
            for item in packet["reviewed_evidence_intakes"]
        },
    }


def _reviewed_evidence_intake_cycle_history_projection(packet: dict) -> dict:
    return {
        "mode": packet["mode"],
        "latest_local_test_result": packet["latest_local_test_result"],
        "reviewed_evidence_intake_summary": {
            "intakes_total": packet["reviewed_evidence_intake_summary"]["intakes_total"],
            "intakes_accepted_for_local_replay": packet["reviewed_evidence_intake_summary"][
                "intakes_accepted_for_local_replay"
            ],
            "intakes_blocked": packet["reviewed_evidence_intake_summary"]["intakes_blocked"],
            "intakes_rejected_after_review": packet["reviewed_evidence_intake_summary"][
                "intakes_rejected_after_review"
            ],
            "intakes_resubmitted_after_review_rejection": packet[
                "reviewed_evidence_intake_summary"
            ]["intakes_resubmitted_after_review_rejection"],
            "intakes_with_multi_attempt_review_history": packet[
                "reviewed_evidence_intake_summary"
            ]["intakes_with_multi_attempt_review_history"],
        },
        "reviewed_evidence_intakes": {
            item["intake_id"]: {
                "intake_status": item["intake_status"],
                "review_outcome": item["review_outcome"],
                "review_rejection_summary": item["review_rejection_summary"],
                "review_cycle_history_summary": item["review_cycle_history_summary"],
                "rejection_reasons": item["rejection_reasons"],
            }
            for item in packet["reviewed_evidence_intakes"]
        },
    }


def test_proof_collection_packet_matches_committed_redacted_snapshot() -> None:
    manifest = proof_artifact_manifest()

    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    expected = proof_collection_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert packet == expected


def test_external_evidence_bundle_packet_matches_committed_redacted_snapshot() -> None:
    bundle = payment_gateway_sandbox_external_evidence_bundle()

    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = external_evidence_bundle_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert packet == expected


def test_external_evidence_bundle_packet_surfaces_blocked_handoff_snapshot() -> None:
    bundle = payment_gateway_sandbox_external_evidence_bundle()
    bundle["signed_envelopes"] = []

    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = external_evidence_bundle_blocked_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert packet == expected


def test_proof_collection_packet_surfaces_rejected_udhaar_metadata_snapshot() -> None:
    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=[
            {
                "artifact_id": "udhaar_settlement_evidence",
                "pilot_period": "2026-05",
                "invoice_count": 0,
                "settled_amount": "0.00",
                "unsettled_amount": "12.50",
                "bank_or_gateway_reconciliation_reference": "redacted-bank-recon-1",
                "owner_or_accountant_reviewer": "redacted-reviewer-1",
                "redaction_confirmed": True,
            }
        ]
    )
    expected = rejected_proof_collection_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert packet == expected


def test_external_evidence_bundle_packet_blocks_on_rejected_artifact_metadata_snapshot() -> None:
    bundle = payment_gateway_sandbox_external_evidence_bundle()
    bundle["artifacts"] = [
        {
            "artifact_id": "provider_sandbox_adapter_evidence",
            "artifact_path_or_reference": "redacted://payment_gateway/razorpay/payment_txn_6023a1f90409",
            "provider": "razorpay",
            "sandbox_or_production_like_tenant": "sandbox",
            "run_timestamp": "2026-05-23T10:30:00+05:30",
            "operator_or_accountant_reviewer": "redacted-ops-reviewer-1",
            "redaction_confirmed": False,
        }
    ]

    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = external_evidence_bundle_rejected_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert packet == expected


def test_external_evidence_bundle_packet_matches_mixed_snapshot_chain_snapshot() -> None:
    reviewer_keys = [
        {
            "reviewer": "operator_or_accountant_reviewer",
            "signer_key_reference": "redacted-reviewer-key-1",
            "key_status": "active",
        }
    ]
    first_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-1",
        recorded_at="2026-05-23T10:25:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="GENESIS",
    )
    second_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-2",
        recorded_at="2026-05-23T10:30:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash=first_snapshot["snapshot_hash"],
    )
    second_snapshot["previous_snapshot_hash"] = "WRONG"
    bundle = payment_gateway_sandbox_external_evidence_bundle()
    bundle["reviewer_key_registry_snapshots"] = [first_snapshot, second_snapshot]

    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = external_evidence_bundle_mixed_snapshot_chain_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert packet == expected


def test_external_evidence_bundle_packet_matches_unverified_snapshot_chain_snapshot() -> None:
    reviewer_keys = [
        {
            "reviewer": "operator_or_accountant_reviewer",
            "signer_key_reference": "redacted-reviewer-key-1",
            "key_status": "active",
        }
    ]
    first_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-1",
        recorded_at="2026-05-23T10:25:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="WRONG",
    )
    second_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-2",
        recorded_at="2026-05-23T10:30:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="ALSO-WRONG",
    )
    bundle = payment_gateway_sandbox_external_evidence_bundle()
    bundle["reviewer_key_registry_snapshots"] = [first_snapshot, second_snapshot]

    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = external_evidence_bundle_unverified_snapshot_chain_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert packet == expected


def test_external_evidence_bundle_packet_matches_combined_rejection_snapshot() -> None:
    reviewer_keys = [
        {
            "reviewer": "operator_or_accountant_reviewer",
            "signer_key_reference": "redacted-reviewer-key-1",
            "key_status": "active",
        }
    ]
    first_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-1",
        recorded_at="2026-05-23T10:25:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="WRONG",
    )
    second_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-2",
        recorded_at="2026-05-23T10:30:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="ALSO-WRONG",
    )
    bundle = payment_gateway_sandbox_external_evidence_bundle()
    bundle["redaction_confirmed"] = False
    bundle["artifacts"] = [
        {
            "artifact_id": "provider_sandbox_adapter_evidence",
            "artifact_path_or_reference": "redacted://payment_gateway/razorpay/payment_txn_6023a1f90409",
            "provider": "razorpay",
            "sandbox_or_production_like_tenant": "sandbox",
            "run_timestamp": "2026-05-23T10:30:00+05:30",
            "operator_or_accountant_reviewer": "redacted-ops-reviewer-1",
            "redaction_confirmed": False,
        }
    ]
    bundle["reviewer_key_registry_snapshots"] = [first_snapshot, second_snapshot]

    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = external_evidence_bundle_combined_rejection_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert packet == expected


def test_reviewed_evidence_intake_packet_matches_committed_redacted_snapshot() -> None:
    intake = gst_sandbox_reviewed_evidence_intake()

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected
    assert packet["reviewed_evidence_intake_summary"]["intakes_accepted_for_local_replay"] == 1


def test_reviewed_evidence_intake_packet_matches_blocked_snapshot() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["session_reference"] = ""
    intake["subject_metadata"]["portal_reference"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_blocked_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected
    assert packet["reviewed_evidence_intake_summary"]["intakes_blocked"] == 1


def test_payment_reviewed_evidence_intake_packet_matches_provider_blocked_snapshot() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["session_reference"] = ""
    intake["subject_metadata"]["portal_reference"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = payment_reviewed_evidence_intake_blocked_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_gst_reviewed_evidence_intake_packet_matches_provider_blocked_snapshot() -> None:
    intake = gst_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["session_reference"] = ""
    intake["subject_metadata"]["gstin"] = ""
    intake["filing_identity_metadata"]["gstin"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = gst_reviewed_evidence_intake_blocked_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_rejected_after_review_snapshot() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_rejected"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-1"
    intake["review_rejection_reasons"] = ["settlement_window_mismatch"]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_rejected_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_reopened_after_review_snapshot() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-1"
    intake["review_rejection_reasons"] = ["settlement_window_mismatch"]
    intake["review_resubmission_reference"] = "redacted-payment-review-resubmission-1"

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_reopened_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_invalid_resubmission_snapshot() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-1"
    intake["review_rejection_reasons"] = ["settlement_window_mismatch"]
    intake["review_resubmission_reference"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_invalid_resubmission_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_repeated_rejection_snapshot() -> None:
    intake = whatsapp_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_rejected"
    intake["review_rejection_reference"] = "redacted-whatsapp-review-rejection-2"
    intake["review_rejection_reasons"] = ["template_reference_still_mismatched"]
    intake["review_resubmission_reference"] = "redacted-whatsapp-review-resubmission-1"

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_repeated_rejection_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_whatsapp_reviewed_evidence_intake_packet_matches_provider_blocked_snapshot() -> None:
    intake = whatsapp_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["login_reference"] = ""
    intake["subject_metadata"]["subject_reference"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = whatsapp_reviewed_evidence_intake_blocked_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_tally_reviewed_evidence_intake_packet_matches_provider_blocked_snapshot() -> None:
    intake = tally_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["login_surface"] = ""
    intake["subject_metadata"]["subject_scope"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = tally_reviewed_evidence_intake_blocked_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_mixed_provider_snapshot() -> None:
    accepted_gst = gst_sandbox_reviewed_evidence_intake()

    blocked_payment = payment_gateway_sandbox_reviewed_evidence_intake()
    blocked_payment["review_outcome"] = "metadata_review_rejected"
    blocked_payment["review_rejection_reference"] = "redacted-payment-review-rejection-1"
    blocked_payment["review_rejection_reasons"] = ["settlement_window_mismatch"]

    blocked_whatsapp = whatsapp_sandbox_reviewed_evidence_intake()
    blocked_whatsapp["operator_login_metadata"]["login_reference"] = ""
    blocked_whatsapp["subject_metadata"]["subject_reference"] = ""

    blocked_tally = tally_sandbox_reviewed_evidence_intake()
    blocked_tally["operator_login_metadata"]["login_surface"] = ""
    blocked_tally["subject_metadata"]["subject_scope"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[
            accepted_gst,
            blocked_payment,
            blocked_whatsapp,
            blocked_tally,
        ],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_mixed_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_mixed_reopened_provider_snapshot() -> None:
    accepted_gst = gst_sandbox_reviewed_evidence_intake()

    reopened_payment = payment_gateway_sandbox_reviewed_evidence_intake()
    reopened_payment["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    reopened_payment["review_rejection_reference"] = "redacted-payment-review-rejection-1"
    reopened_payment["review_rejection_reasons"] = ["settlement_window_mismatch"]
    reopened_payment["review_resubmission_reference"] = (
        "redacted-payment-review-resubmission-1"
    )

    rejected_whatsapp = whatsapp_sandbox_reviewed_evidence_intake()
    rejected_whatsapp["review_outcome"] = "metadata_review_rejected"
    rejected_whatsapp["review_rejection_reference"] = (
        "redacted-whatsapp-review-rejection-1"
    )
    rejected_whatsapp["review_rejection_reasons"] = ["template_reference_mismatch"]

    blocked_tally = tally_sandbox_reviewed_evidence_intake()
    blocked_tally["operator_login_metadata"]["login_surface"] = ""
    blocked_tally["subject_metadata"]["subject_scope"] = ""

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[
            accepted_gst,
            reopened_payment,
            rejected_whatsapp,
            blocked_tally,
        ],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_mixed_reopened_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_mixed_rejection_cycle_snapshot() -> None:
    accepted_gst = gst_sandbox_reviewed_evidence_intake()

    invalid_payment = payment_gateway_sandbox_reviewed_evidence_intake()
    invalid_payment["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    invalid_payment["review_rejection_reference"] = "redacted-payment-review-rejection-1"
    invalid_payment["review_rejection_reasons"] = ["settlement_window_mismatch"]
    invalid_payment["review_resubmission_reference"] = ""

    repeated_whatsapp = whatsapp_sandbox_reviewed_evidence_intake()
    repeated_whatsapp["review_outcome"] = "metadata_review_rejected"
    repeated_whatsapp["review_rejection_reference"] = (
        "redacted-whatsapp-review-rejection-2"
    )
    repeated_whatsapp["review_rejection_reasons"] = [
        "template_reference_still_mismatched"
    ]
    repeated_whatsapp["review_resubmission_reference"] = (
        "redacted-whatsapp-review-resubmission-1"
    )

    reopened_tally = tally_sandbox_reviewed_evidence_intake()
    reopened_tally["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    reopened_tally["review_rejection_reference"] = "redacted-tally-review-rejection-1"
    reopened_tally["review_rejection_reasons"] = ["company_reference_not_approved"]
    reopened_tally["review_resubmission_reference"] = (
        "redacted-tally-review-resubmission-1"
    )

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[
            accepted_gst,
            invalid_payment,
            repeated_whatsapp,
            reopened_tally,
        ],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_mixed_rejection_cycle_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_snapshot_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_multi_attempt_resubmission_snapshot() -> None:
    intake = gst_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-gst-review-rejection-2"
    intake["review_rejection_reasons"] = ["filing_period_still_misaligned"]
    intake["review_resubmission_reference"] = "redacted-gst-review-resubmission-2"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-gst-review-rejection-1",
            "review_rejection_reasons": ["filing_period_mismatch"],
            "review_resubmission_reference": "redacted-gst-review-resubmission-1",
        }
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_multi_attempt_resubmission_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_cycle_history_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_multi_attempt_rejection_snapshot() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_rejected"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-2"
    intake["review_rejection_reasons"] = ["settlement_window_still_mismatched"]
    intake["review_resubmission_reference"] = "redacted-payment-review-resubmission-1"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-payment-review-rejection-1",
            "review_rejection_reasons": ["settlement_window_mismatch"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-1",
        }
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_multi_attempt_rejection_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_cycle_history_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_long_chain_resubmission_snapshot() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-3"
    intake["review_rejection_reasons"] = ["settlement_reference_still_incomplete"]
    intake["review_resubmission_reference"] = "redacted-payment-review-resubmission-3"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-payment-review-rejection-1",
            "review_rejection_reasons": ["settlement_window_mismatch"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-1",
        },
        {
            "review_rejection_reference": "redacted-payment-review-rejection-2",
            "review_rejection_reasons": ["gateway_reference_missing"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-2",
        },
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_long_chain_resubmission_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_cycle_history_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_long_chain_rejection_snapshot() -> None:
    intake = whatsapp_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_rejected"
    intake["review_rejection_reference"] = "redacted-whatsapp-review-rejection-3"
    intake["review_rejection_reasons"] = ["template_approval_still_not_linked"]
    intake["review_resubmission_reference"] = "redacted-whatsapp-review-resubmission-2"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-whatsapp-review-rejection-1",
            "review_rejection_reasons": ["template_reference_mismatch"],
            "review_resubmission_reference": "redacted-whatsapp-review-resubmission-1",
        },
        {
            "review_rejection_reference": "redacted-whatsapp-review-rejection-2",
            "review_rejection_reasons": ["message_window_not_documented"],
            "review_resubmission_reference": "redacted-whatsapp-review-resubmission-2",
        },
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_long_chain_rejection_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_cycle_history_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_mixed_history_invalid_snapshot() -> None:
    intake = tally_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-tally-review-rejection-3"
    intake["review_rejection_reasons"] = ["company_scope_still_incomplete"]
    intake["review_resubmission_reference"] = "redacted-tally-review-resubmission-3"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-tally-review-rejection-1",
            "review_rejection_reasons": ["company_reference_not_approved"],
            "review_resubmission_reference": "redacted-tally-review-resubmission-1",
        },
        {
            "review_rejection_reference": "redacted-tally-review-rejection-2",
            "review_rejection_reasons": ["ledger_mapping_missing"],
            "review_resubmission_reference": "",
        },
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_mixed_history_invalid_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_cycle_history_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_multi_invalid_history_snapshot() -> None:
    intake = tally_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-tally-review-rejection-4"
    intake["review_rejection_reasons"] = ["company_scope_and_mapping_still_incomplete"]
    intake["review_resubmission_reference"] = "redacted-tally-review-resubmission-4"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-tally-review-rejection-1",
            "review_rejection_reasons": ["company_reference_not_approved"],
            "review_resubmission_reference": "redacted-tally-review-resubmission-1",
        },
        {
            "review_rejection_reference": "redacted-tally-review-rejection-2",
            "review_rejection_reasons": ["ledger_mapping_missing"],
            "review_resubmission_reference": "",
        },
        {
            "review_rejection_reference": "",
            "review_rejection_reasons": ["review_packet_missing_reference"],
            "review_resubmission_reference": "",
        },
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_multi_invalid_history_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_cycle_history_projection(packet) == expected


def test_reviewed_evidence_intake_packet_matches_mixed_type_history_snapshot() -> None:
    intake = payment_gateway_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-payment-review-rejection-4"
    intake["review_rejection_reasons"] = ["settlement_metadata_still_incomplete"]
    intake["review_resubmission_reference"] = "redacted-payment-review-resubmission-4"
    intake["prior_review_cycles"] = [
        {
            "review_rejection_reference": "redacted-payment-review-rejection-1",
            "review_rejection_reasons": ["settlement_window_mismatch"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-1",
        },
        "malformed-history-cycle",
        {
            "review_rejection_reference": "redacted-payment-review-rejection-3",
            "review_rejection_reasons": ["gateway_reference_missing"],
            "review_resubmission_reference": "redacted-payment-review-resubmission-3",
        },
    ]

    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    expected = reviewed_evidence_intake_mixed_type_history_packet_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _reviewed_evidence_intake_cycle_history_projection(packet) == expected


def test_proof_review_handoff_packet_routes_metadata_without_readiness_claim() -> None:
    packet = build_benchmark_proof_review_handoff_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=proof_artifact_manifest()["artifacts"],
        metadata_manifest_files_read=True,
    )
    artifact_queue = {item["artifact_id"]: item for item in packet["artifact_review_queue"]}
    gate_queue = {item["gate"]: item for item in packet["done_state_gate_review_queue"]}

    assert packet["mode"] == "local_proof_review_handoff_packet"
    assert packet["review_scope"] == "metadata_review_only"
    assert packet["benchmark_parity"] is False
    assert packet["ship_ready"] is False
    assert packet["artifact_review_summary"] == {
        "artifact_requirements_total": 7,
        "artifact_requirements_ready_for_external_review": 2,
        "artifact_requirements_missing_metadata": 5,
        "artifact_requirements_rejected_metadata": 0,
        "artifact_requirements_proven": 0,
    }
    assert artifact_queue["provider_sandbox_adapter_evidence"]["required_reviewer"] == (
        "operator_or_accountant_reviewer"
    )
    assert artifact_queue["provider_sandbox_adapter_evidence"]["review_status"] == (
        "pending_external_review"
    )
    assert artifact_queue["owner_briefing_delivery_evidence"]["required_reviewer"] == "external_reviewer"
    assert artifact_queue["low_literacy_pilot_evidence"]["review_status"] == (
        "blocked_until_metadata_submitted"
    )
    assert gate_queue["owner_trusts_agent_summaries"]["review_status"] == "pending_external_review"
    assert gate_queue["every_rupee_udhaar_settled"]["review_status"] == (
        "blocked_until_required_metadata_submitted"
    )
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False
    expected = proof_review_handoff_packet_snapshot()
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _handoff_snapshot_projection(packet) == expected


def test_proof_review_decision_packet_accepts_ready_external_reviewer_decision_only() -> None:
    packet = build_benchmark_proof_review_decision_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=proof_artifact_manifest()["artifacts"],
        review_decisions=[
            {
                "artifact_id": "owner_briefing_delivery_evidence",
                "decision": "approved",
                "reviewer": "external_reviewer",
                "review_reference": "redacted-review-decision-1",
                "reviewed_at": "2026-05-22T09:30:00+05:30",
                "redaction_confirmed": True,
            },
            {
                "artifact_id": "provider_sandbox_adapter_evidence",
                "decision": "approved",
                "reviewer": "wrong_reviewer",
                "review_reference": "redacted-review-decision-2",
                "reviewed_at": "2026-05-22T09:31:00+05:30",
                "redaction_confirmed": True,
            },
        ],
        metadata_manifest_files_read=True,
    )
    decisions = {item["artifact_id"]: item for item in packet["artifact_review_decisions"]}
    gate_decisions = {item["gate"]: item for item in packet["done_state_gate_review_decisions"]}

    assert packet["artifact_review_decision_summary"] == {
        "review_decisions_total": 2,
        "review_decisions_accepted": 1,
        "review_decisions_rejected": 0,
        "review_decisions_blocked": 1,
        "artifacts_approved_by_external_review": 1,
        "artifacts_rejected_by_external_review": 0,
        "artifacts_proven": 0,
    }
    assert decisions["owner_briefing_delivery_evidence"]["decision_status"] == "external_review_approved"
    assert decisions["provider_sandbox_adapter_evidence"]["decision_status"] == "external_review_blocked"
    assert decisions["provider_sandbox_adapter_evidence"]["rejection_reasons"] == [
        "reviewer_mismatch: expected operator_or_accountant_reviewer"
    ]
    assert gate_decisions["owner_trusts_agent_summaries"]["review_decision_status"] == (
        "external_review_complete_not_proven"
    )
    assert gate_decisions["reliable_7am_owner_briefing"]["approved_artifact_ids"] == [
        "owner_briefing_delivery_evidence"
    ]
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False
    expected = proof_review_decision_packet_snapshot()
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _decision_snapshot_projection(packet) == expected


def test_proof_reviewer_assignment_packet_routes_specialized_profiles_without_proof() -> None:
    packet = build_benchmark_proof_reviewer_assignment_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=proof_artifact_manifest()["artifacts"],
        metadata_manifest_files_read=True,
    )
    assignments = {item["artifact_id"]: item for item in packet["reviewer_assignments"]}

    assert packet["mode"] == "local_proof_reviewer_assignment_packet"
    assert packet["reviewer_assignment_summary"] == {
        "artifact_requirements_total": 7,
        "assignments_ready_for_specialized_review": 2,
        "assignments_blocked_until_metadata_ready": 5,
        "artifacts_proven_by_assignment": 0,
    }
    assert assignments["owner_briefing_delivery_evidence"]["reviewer_role"] == "external_reviewer"
    assert assignments["owner_briefing_delivery_evidence"]["specialized_subagent_profile"] == (
        "owner_operating_loop_reviewer"
    )
    assert assignments["owner_briefing_delivery_evidence"]["assignment_status"] == (
        "ready_for_specialized_review"
    )
    assert assignments["low_literacy_pilot_evidence"]["assignment_status"] == (
        "blocked_until_metadata_ready"
    )
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False
    expected = proof_reviewer_assignment_packet_snapshot()
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _assignment_snapshot_projection(packet) == expected


def test_proof_review_decision_ledger_packet_replays_and_blocks_entries_locally() -> None:
    packet = build_benchmark_proof_review_decision_ledger_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=proof_artifact_manifest()["artifacts"],
        review_decision_ledger_entries=[
            {
                "ledger_entry_id": "ledger-owner-briefing-1",
                "recorded_at": "2026-05-22T09:35:00+05:30",
                "decision": {
                    "artifact_id": "owner_briefing_delivery_evidence",
                    "decision": "approved",
                    "reviewer": "external_reviewer",
                    "review_reference": "redacted-review-decision-1",
                    "reviewed_at": "2026-05-22T09:30:00+05:30",
                    "redaction_confirmed": True,
                },
            },
            {
                "ledger_entry_id": "ledger-bad-provider-review",
                "recorded_at": "2026-05-22T09:36:00+05:30",
                "decision": {
                    "artifact_id": "provider_sandbox_adapter_evidence",
                    "decision": "approved",
                    "reviewer": "wrong_reviewer",
                    "review_reference": "redacted-review-decision-2",
                    "reviewed_at": "2026-05-22T09:31:00+05:30",
                    "redaction_confirmed": True,
                },
            },
            {
                "ledger_entry_id": "ledger-invalid-payload",
                "decision": "not-an-object",
            },
        ],
        metadata_manifest_files_read=True,
        decision_ledger_files_read=True,
    )
    entries = {item["ledger_entry_id"]: item for item in packet["review_decision_ledger_entries"]}

    assert packet["mode"] == "local_proof_review_decision_ledger_packet"
    assert packet["review_decision_ledger_summary"] == {
        "ledger_entries_total": 3,
        "ledger_entries_replayed": 1,
        "ledger_entries_blocked": 2,
        "ledger_entries_with_approved_decisions": 1,
        "ledger_entries_with_rejected_decisions": 0,
        "artifacts_proven_by_ledger": 0,
    }
    assert entries["ledger-owner-briefing-1"]["replay_status"] == "replayed"
    assert entries["ledger-owner-briefing-1"]["decision_status"] == "external_review_approved"
    assert entries["ledger-bad-provider-review"]["replay_status"] == "blocked"
    assert entries["ledger-bad-provider-review"]["rejection_reasons"] == [
        "reviewer_mismatch: expected operator_or_accountant_reviewer"
    ]
    assert entries["ledger-invalid-payload"]["replay_status"] == "blocked"
    assert entries["ledger-invalid-payload"]["rejection_reasons"] == [
        "missing_ledger_entry_fields: recorded_at",
        "invalid_decision_payload",
    ]
    assert packet["audit"]["decision_ledger_files_read"] is True
    assert packet["audit"]["artifact_files_read"] is False
    assert packet["audit"]["secret_values_inspected"] is False
    assert packet["audit"]["live_api_called"] is False
    expected = proof_review_decision_ledger_packet_snapshot()
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _ledger_snapshot_projection(packet) == expected


def test_proof_review_signed_envelope_packet_matches_committed_redacted_snapshot() -> None:
    bundle = payment_gateway_sandbox_external_evidence_bundle()

    packet = build_benchmark_proof_review_signed_envelope_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=bundle["artifacts"],
        signed_review_envelopes=bundle["signed_envelopes"],
        reviewer_key_registry_snapshots=bundle["reviewer_key_registry_snapshots"],
        metadata_manifest_files_read=True,
        signed_envelope_files_read=True,
        reviewer_key_registry_snapshot_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = proof_review_signed_envelope_packet_snapshot()

    assert packet["audit"]["reviewer_key_registry_snapshot_chain_verified"] is True
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _signed_envelope_snapshot_projection(packet) == expected


def test_proof_review_signed_envelope_packet_surfaces_tampered_registry_snapshot() -> None:
    bundle = payment_gateway_sandbox_external_evidence_bundle()
    bundle["reviewer_key_registry_snapshots"][0]["previous_snapshot_hash"] = "WRONG"

    packet = build_benchmark_proof_review_signed_envelope_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=bundle["artifacts"],
        signed_review_envelopes=bundle["signed_envelopes"],
        reviewer_key_registry_snapshots=bundle["reviewer_key_registry_snapshots"],
        metadata_manifest_files_read=True,
        signed_envelope_files_read=True,
        reviewer_key_registry_snapshot_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = proof_review_signed_envelope_blocked_packet_snapshot()

    assert packet["audit"]["reviewer_key_registry_snapshot_chain_verified"] is False
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _signed_envelope_snapshot_projection(packet) == expected


def test_proof_review_signed_envelope_packet_surfaces_reviewer_key_rejections_snapshot() -> None:
    packet = build_benchmark_proof_review_signed_envelope_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=[
            {
                "artifact_id": "owner_briefing_delivery_evidence",
                "delivery_period": "2026-05",
                "scheduled_delivery_time": "07:00",
                "successful_delivery_count": 20,
                "missed_delivery_count": 0,
                "owner_acknowledgement_reference": "redacted-owner-review-1",
                "fallback_channel_used": "whatsapp_sandbox",
                "redaction_confirmed": True,
            }
        ],
        signed_review_envelopes=[
            {
                "envelope_id": "signed-revoked-key",
                "signature_scheme": "local_metadata_signature_v1",
                "signer_key_reference": "redacted-revoked-key",
                "signature_reference": "redacted-signature-reference-1",
                "signed_at": "2026-05-22T09:36:00+05:30",
                "decision": {
                    "artifact_id": "owner_briefing_delivery_evidence",
                    "decision": "approved",
                    "reviewer": "external_reviewer",
                    "review_reference": "redacted-review-decision-1",
                    "reviewed_at": "2026-05-22T09:30:00+05:30",
                    "redaction_confirmed": True,
                },
            },
            {
                "envelope_id": "signed-wrong-reviewer-key",
                "signature_scheme": "local_metadata_signature_v1",
                "signer_key_reference": "redacted-accountant-key",
                "signature_reference": "redacted-signature-reference-2",
                "signed_at": "2026-05-22T09:37:00+05:30",
                "decision": {
                    "artifact_id": "owner_briefing_delivery_evidence",
                    "decision": "approved",
                    "reviewer": "external_reviewer",
                    "review_reference": "redacted-review-decision-2",
                    "reviewed_at": "2026-05-22T09:31:00+05:30",
                    "redaction_confirmed": True,
                },
            },
            {
                "envelope_id": "signed-missing-key",
                "signature_scheme": "local_metadata_signature_v1",
                "signer_key_reference": "redacted-unknown-key",
                "signature_reference": "redacted-signature-reference-3",
                "signed_at": "2026-05-22T09:38:00+05:30",
                "decision": {
                    "artifact_id": "owner_briefing_delivery_evidence",
                    "decision": "approved",
                    "reviewer": "external_reviewer",
                    "review_reference": "redacted-review-decision-3",
                    "reviewed_at": "2026-05-22T09:32:00+05:30",
                    "redaction_confirmed": True,
                },
            },
        ],
        reviewer_key_registry=[
            {
                "reviewer": "external_reviewer",
                "signer_key_reference": "redacted-revoked-key",
                "key_status": "revoked",
            },
            {
                "reviewer": "accountant_reviewer",
                "signer_key_reference": "redacted-accountant-key",
                "key_status": "active",
            },
        ],
    )
    expected = proof_review_signed_envelope_key_rejections_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _signed_envelope_snapshot_projection(packet) == expected


def test_proof_review_signed_envelope_packet_surfaces_invalid_decision_with_allowed_key_snapshot(
) -> None:
    packet = build_benchmark_proof_review_signed_envelope_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=[
            {
                "artifact_id": "owner_briefing_delivery_evidence",
                "delivery_period": "2026-05",
                "scheduled_delivery_time": "07:00",
                "successful_delivery_count": 20,
                "missed_delivery_count": 0,
                "owner_acknowledgement_reference": "redacted-owner-review-1",
                "fallback_channel_used": "whatsapp_sandbox",
                "redaction_confirmed": True,
            }
        ],
        signed_review_envelopes=[
            {
                "envelope_id": "signed-invalid-decision-1",
                "signature_scheme": "local_metadata_signature_v1",
                "signer_key_reference": "redacted-reviewer-key-1",
                "signature_reference": "redacted-signature-reference-1",
                "signed_at": "2026-05-22T09:36:00+05:30",
                "decision": {
                    "artifact_id": "owner_briefing_delivery_evidence",
                    "decision": "approved",
                    "reviewer": "external_reviewer",
                    "review_reference": "redacted-review-decision-1",
                    "reviewed_at": "2026-05-22T09:30:00+05:30",
                    "redaction_confirmed": False,
                },
            }
        ],
        reviewer_key_registry=[
            {
                "reviewer": "external_reviewer",
                "signer_key_reference": "redacted-reviewer-key-1",
                "key_status": "active",
            }
        ],
    )
    expected = proof_review_signed_envelope_invalid_decision_snapshot()

    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _signed_envelope_snapshot_projection(packet) == expected


def test_proof_review_signed_envelope_packet_matches_combined_failure_snapshot() -> None:
    reviewer_keys = [
        {
            "reviewer": "external_reviewer",
            "signer_key_reference": "redacted-reviewer-key-1",
            "key_status": "active",
        }
    ]
    first_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-1",
        recorded_at="2026-05-22T10:00:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="WRONG",
    )
    second_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-2",
        recorded_at="2026-05-22T10:05:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="ALSO-WRONG",
    )
    packet = build_benchmark_proof_review_signed_envelope_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=[
            {
                "artifact_id": "owner_briefing_delivery_evidence",
                "delivery_period": "2026-05",
                "scheduled_delivery_time": "07:00",
                "successful_delivery_count": 20,
                "missed_delivery_count": 0,
                "owner_acknowledgement_reference": "redacted-owner-review-1",
                "fallback_channel_used": "whatsapp_sandbox",
                "redaction_confirmed": True,
            }
        ],
        signed_review_envelopes=[
            {
                "envelope_id": "signed-missing-signature-reference",
                "signature_scheme": "local_metadata_signature_v1",
                "signer_key_reference": "redacted-reviewer-key-1",
                "signed_at": "2026-05-22T09:36:00+05:30",
                "decision": {
                    "artifact_id": "owner_briefing_delivery_evidence",
                    "decision": "approved",
                    "reviewer": "external_reviewer",
                    "review_reference": "redacted-review-decision-1",
                    "reviewed_at": "2026-05-22T09:30:00+05:30",
                    "redaction_confirmed": True,
                },
            }
        ],
        reviewer_key_registry_snapshots=[first_snapshot, second_snapshot],
        metadata_manifest_files_read=True,
        signed_envelope_files_read=True,
        reviewer_key_registry_snapshot_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = proof_review_signed_envelope_combined_failure_snapshot()

    assert packet["audit"]["reviewer_key_registry_snapshot_chain_verified"] is False
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _signed_envelope_snapshot_projection(packet) == expected


def test_proof_review_signed_envelope_packet_matches_verified_multi_snapshot_chain_snapshot(
) -> None:
    reviewer_keys = [
        {
            "reviewer": "operator_or_accountant_reviewer",
            "signer_key_reference": "redacted-reviewer-key-1",
            "key_status": "active",
        }
    ]
    first_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-1",
        recorded_at="2026-05-23T10:25:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="GENESIS",
    )
    second_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-2",
        recorded_at="2026-05-23T10:30:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash=first_snapshot["snapshot_hash"],
    )
    bundle = payment_gateway_sandbox_external_evidence_bundle()

    packet = build_benchmark_proof_review_signed_envelope_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=bundle["artifacts"],
        signed_review_envelopes=bundle["signed_envelopes"],
        reviewer_key_registry_snapshots=[first_snapshot, second_snapshot],
        metadata_manifest_files_read=True,
        signed_envelope_files_read=True,
        reviewer_key_registry_snapshot_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = proof_review_signed_envelope_multi_snapshot_chain_snapshot()

    assert packet["audit"]["reviewer_key_registry_snapshot_chain_verified"] is True
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _signed_envelope_snapshot_projection(packet) == expected


def test_proof_review_signed_envelope_packet_falls_back_to_latest_verified_snapshot_in_mixed_chain_snapshot(
) -> None:
    reviewer_keys = [
        {
            "reviewer": "operator_or_accountant_reviewer",
            "signer_key_reference": "redacted-reviewer-key-1",
            "key_status": "active",
        }
    ]
    first_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-1",
        recorded_at="2026-05-23T10:25:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="GENESIS",
    )
    second_snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id="registry-snapshot-payment-demo-2",
        recorded_at="2026-05-23T10:30:00+05:30",
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash=first_snapshot["snapshot_hash"],
    )
    second_snapshot["previous_snapshot_hash"] = "WRONG"
    bundle = payment_gateway_sandbox_external_evidence_bundle()

    packet = build_benchmark_proof_review_signed_envelope_packet(
        latest_local_test_result=_LATEST_LOCAL_TEST_RESULT,
        provided_artifacts=bundle["artifacts"],
        signed_review_envelopes=bundle["signed_envelopes"],
        reviewer_key_registry_snapshots=[first_snapshot, second_snapshot],
        metadata_manifest_files_read=True,
        signed_envelope_files_read=True,
        reviewer_key_registry_snapshot_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    expected = proof_review_signed_envelope_mixed_snapshot_chain_snapshot()

    assert packet["audit"]["reviewer_key_registry_snapshot_chain_verified"] is False
    assert_redaction_safe_payload(expected, allowed_key_paths=_ALLOWED_AUDIT_KEY_PATHS)
    assert _signed_envelope_snapshot_projection(packet) == expected
