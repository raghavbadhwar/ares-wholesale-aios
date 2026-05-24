from __future__ import annotations

from apps.ares.ares.connectors.tally_sync_adapter import (
    TALLY_BRIDGE_ADAPTER_LIMITATION,
    TALLY_BRIDGE_EXECUTION_HARNESS_LIMITATION,
    TALLY_BUSY_PREFLIGHT_ENV_NAMES,
    build_tally_bridge_execution_harness,
    build_tally_bridge_external_evidence_bundle,
    build_tally_bridge_proof_artifact_metadata,
    build_tally_bridge_proof_metadata_manifest,
    build_tally_bridge_reviewed_evidence_intake,
    ingest_tally_bridge_payload,
)
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.accounting_sync import LOCAL_SYNC_LIMITATION
from apps.ares.ares.connectors.proof_packets import (
    build_benchmark_external_evidence_bundle_packet,
    build_benchmark_proof_collection_packet,
    build_benchmark_reviewed_evidence_intake_packet,
)
from tests.ares.support import (
    tally_odbc_manual_review_rows,
    tally_sandbox_external_evidence_bundle,
    tally_sandbox_proof_artifact,
    tally_sandbox_proof_manifest,
    tally_sandbox_reviewed_evidence_intake,
    tally_status_xml_text,
)


def test_should_route_xml_status_receipt_with_company_selection_into_audit_only_normalization() -> None:
    repo = InMemoryRepository()

    result = ingest_tally_bridge_payload(
        repository=repo,
        client_id="demo",
        system="tally",
        bridge_mode="xml_status_receipt",
        payload=tally_status_xml_text(),
        company_selection={"company_name": "Demo Traders Pvt Ltd", "company_id": "cmp_demo_1"},
    )

    assert result["status"] == "accepted"
    assert result["company_selection"] == {
        "company_name": "Demo Traders Pvt Ltd",
        "company_id": "cmp_demo_1",
        "source": "operator_selected",
    }
    assert result["adapter"] == {
        "connector": "tally_sync_adapter",
        "bridge_mode_routed": "xml_status_receipt",
        "live_bridge_called": False,
        "company_mutation_performed": False,
        "limitation": TALLY_BRIDGE_ADAPTER_LIMITATION,
        "normalization_limitation": LOCAL_SYNC_LIMITATION,
    }
    assert repo.list_action_logs()[0].action_type == "normalize_accounting_bridge_payload"


def test_should_route_odbc_rowset_with_manual_review_signal() -> None:
    repo = InMemoryRepository()

    result = ingest_tally_bridge_payload(
        repository=repo,
        client_id="demo",
        system="busy",
        bridge_mode="odbc_rowset",
        payload=tally_odbc_manual_review_rows(),
        company_selection={"company_name": "Busy Sandbox", "source": "odbc_company_hint"},
    )

    assert result["status"] == "needs_manual_review"
    assert result["summary"] == {"records_total": 2, "accepted_records": 1, "manual_review_records": 1}
    assert result["company_selection"] == {
        "company_name": "Busy Sandbox",
        "company_id": None,
        "source": "odbc_company_hint",
    }
    assert result["adapter"]["bridge_mode_routed"] == "odbc_rowset"
    assert result["adapter"]["live_bridge_called"] is False


def test_should_require_company_name_for_local_bridge_routing() -> None:
    repo = InMemoryRepository()

    try:
        ingest_tally_bridge_payload(
            repository=repo,
            client_id="demo",
            system="tally",
            bridge_mode="xml_status_receipt",
            payload=tally_status_xml_text(),
            company_selection={"company_id": "missing_name"},
        )
    except ValueError as exc:
        assert "company_name is required" in str(exc)
    else:
        raise AssertionError("Expected missing company_name to be rejected")


def test_should_build_xml_execution_harness_with_company_selection_and_proof_safe_transcript() -> None:
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
    assert result["required_env_names"] == [
        "TALLY_SANDBOX_BASE_URL",
        "TALLY_SANDBOX_COMPANY_NAME",
        "TALLY_SANDBOX_BRIDGE_MODE",
        "TALLY_SANDBOX_XML_GATEWAY_URL",
    ]
    assert result["missing_env_names"] == []
    assert result["bridge_route"] == {
        "connector": "tally_sync_adapter",
        "system": "tally",
        "bridge_mode": "xml_status_receipt",
        "transport": "xml_gateway",
        "company_name": "Demo Traders Pvt Ltd",
    }
    assert result["proof_transcript"]["proof_safe"] is True
    assert result["proof_transcript"]["raw_payload_persisted"] is False
    assert result["proof_transcript"]["payload_reference"] == "redacted://tally/sandbox/xml-status-1"
    assert result["audit"]["limitation"] == TALLY_BRIDGE_EXECUTION_HARNESS_LIMITATION


def test_should_block_odbc_execution_harness_when_mode_specific_env_contract_is_incomplete() -> None:
    result = build_tally_bridge_execution_harness(
        system="busy",
        bridge_mode="odbc_rowset",
        company_selection={"company_name": "Busy Sandbox", "source": "odbc_company_hint"},
        payload_reference="redacted://busy/sandbox/odbc-status-1",
        configured_env_names={
            "BUSY_SANDBOX_BASE_URL",
            "BUSY_SANDBOX_COMPANY_NAME",
        },
    )

    assert result["status"] == "blocked"
    assert result["can_run_local_execution_harness"] is False
    assert result["required_env_names"] == [
        "BUSY_SANDBOX_BASE_URL",
        "BUSY_SANDBOX_COMPANY_NAME",
        "BUSY_SANDBOX_BRIDGE_MODE",
        "BUSY_SANDBOX_ODBC_DSN",
    ]
    assert result["missing_env_names"] == [
        "BUSY_SANDBOX_BRIDGE_MODE",
        "BUSY_SANDBOX_ODBC_DSN",
    ]
    assert "missing bridge environment names" in result["blocked_reasons"][0]


def test_should_publish_repo_wide_tally_busy_preflight_env_contract() -> None:
    assert TALLY_BUSY_PREFLIGHT_ENV_NAMES == [
        "TALLY_SANDBOX_BASE_URL",
        "BUSY_SANDBOX_BASE_URL",
        "TALLY_BUSY_SANDBOX_SYSTEM",
        "TALLY_BUSY_SANDBOX_COMPANY_NAME",
        "TALLY_BUSY_SANDBOX_BRIDGE_MODE",
        "TALLY_BUSY_SANDBOX_XML_GATEWAY_URL",
        "TALLY_BUSY_SANDBOX_ODBC_DSN",
    ]


def test_should_build_proof_safe_tally_bridge_artifact_metadata_accepted_by_proof_packet() -> None:
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
    packet = build_benchmark_proof_collection_packet(provided_artifacts=[artifact])
    requirement = {
        item["artifact_id"]: item for item in packet["artifact_requirements"]
    }["provider_sandbox_adapter_evidence"]

    assert artifact == {
        "artifact_id": "provider_sandbox_adapter_evidence",
        "artifact_path_or_reference": f"redacted://tally_busy/{harness['proof_transcript']['transcript_id']}",
        "provider": "tally_busy",
        "sandbox_or_production_like_tenant": "sandbox",
        "run_timestamp": "2026-05-23T10:00:00+05:30",
        "operator_or_accountant_reviewer": "redacted-ops-reviewer-1",
        "redaction_confirmed": True,
    }
    assert requirement["status"] == "metadata_accepted_for_review"


def test_should_build_tally_proof_metadata_manifest_for_operator_handoff() -> None:
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

    manifest = build_tally_bridge_proof_metadata_manifest(
        execution_harness=harness,
        run_timestamp="2026-05-23T10:00:00+05:30",
        reviewer_reference="redacted-ops-reviewer-1",
    )
    packet = build_benchmark_proof_collection_packet(
        provided_artifacts=manifest["artifacts"],
        metadata_manifest_files_read=True,
    )
    requirement = {item["artifact_id"]: item for item in packet["artifact_requirements"]}[
        "provider_sandbox_adapter_evidence"
    ]

    assert manifest["generated_from"] == "tally_sync_adapter"
    assert manifest["redaction_confirmed"] is True
    assert len(manifest["artifacts"]) == 1
    assert manifest["artifacts"][0]["provider"] == "tally_busy"
    assert requirement["status"] == "metadata_accepted_for_review"
    assert packet["audit"]["metadata_manifest_files_read"] is True


def test_tally_proof_artifact_and_manifest_fixtures_are_accepted_by_proof_packet() -> None:
    artifact = tally_sandbox_proof_artifact()
    manifest = tally_sandbox_proof_manifest()
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


def test_should_build_tally_external_evidence_bundle_for_operator_handoff() -> None:
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
    bundle_item = packet["external_evidence_bundles"][0]

    assert bundle["bundle_id"].startswith("external-evidence-bundle-tally-")
    assert bundle["redaction_confirmed"] is True
    assert len(bundle["artifacts"]) == 1
    assert len(bundle["signed_envelopes"]) == 1
    assert len(bundle["reviewer_key_registry_snapshots"]) == 1
    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert bundle_item["bundle_status"] == "accepted_for_external_handoff"
    assert bundle_item["proof_collection_summary"]["artifact_requirements_accepted"] == 1
    assert bundle_item["signed_envelope_summary"]["signed_envelopes_accepted"] == 1
    assert bundle_item["review_decision_summary"]["review_decisions_accepted"] == 1
    assert bundle_item["reviewer_key_registry_snapshot_summary"]["registry_snapshots_verified"] == 1
    assert packet["audit"]["external_evidence_bundle_files_read"] is True


def test_tally_external_evidence_bundle_fixture_is_accepted_for_handoff() -> None:
    bundle = tally_sandbox_external_evidence_bundle()
    packet = build_benchmark_external_evidence_bundle_packet(
        latest_local_test_result="243 passed in batches",
        evidence_bundles=[bundle],
        external_evidence_bundle_files_read=True,
        verify_reviewer_key_registry_snapshot_chain=True,
    )
    bundle_item = packet["external_evidence_bundles"][0]

    assert packet["external_evidence_bundle_summary"]["bundles_accepted_for_handoff"] == 1
    assert bundle_item["bundle_status"] == "accepted_for_external_handoff"
    assert bundle_item["signed_envelope_summary"]["signed_envelopes_accepted"] == 1
    assert bundle_item["review_decision_summary"]["review_decisions_accepted"] == 1
    assert bundle_item["reviewer_key_registry_snapshot_summary"]["registry_snapshots_verified"] == 1


def test_should_build_tally_reviewed_evidence_intake_for_local_replay() -> None:
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

    intake = build_tally_bridge_reviewed_evidence_intake(
        execution_harness=harness,
        external_evidence_bundle=bundle,
        reviewed_at="2026-05-23T12:30:00+05:30",
        reviewer_reference="redacted-tally-reviewer-1",
    )
    packet = build_benchmark_reviewed_evidence_intake_packet(
        latest_local_test_result="244 passed in batches",
        reviewed_evidence_intakes=[intake],
        reviewed_evidence_intake_files_read=True,
    )
    item = packet["reviewed_evidence_intakes"][0]

    assert intake["provider"] == "tally_busy"
    assert intake["subject_metadata_kind"] == "tally_bridge_identity"
    assert item["intake_status"] == "accepted_for_local_review_replay"
    assert item["subject_metadata_summary"]["subject_identifier"] == "cmp_demo_1"
    assert item["subject_metadata_summary"]["metadata_ready"] is True


def test_tally_reviewed_evidence_intake_fixture_is_accepted_by_packet() -> None:
    intake = tally_sandbox_reviewed_evidence_intake()
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


def test_tally_reviewed_evidence_intake_blocks_on_missing_login_surface_and_bridge_scope() -> None:
    intake = tally_sandbox_reviewed_evidence_intake()
    intake["operator_login_metadata"]["login_surface"] = ""
    intake["subject_metadata"]["subject_scope"] = ""

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
        "operator_login_metadata.missing_field:login_surface",
        "subject_metadata.missing_scope",
    ]


def test_tally_reviewed_evidence_intake_blocks_after_reviewer_rejection_with_valid_metadata() -> None:
    intake = tally_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_rejected"
    intake["review_rejection_reference"] = "redacted-tally-review-rejection-1"
    intake["review_rejection_reasons"] = ["company_reference_not_approved"]

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
        "review_rejection_reason:company_reference_not_approved",
    ]


def test_tally_reviewed_evidence_intake_reopens_after_corrected_resubmission() -> None:
    intake = tally_sandbox_reviewed_evidence_intake()
    intake["review_outcome"] = "metadata_review_resubmitted_after_rejection"
    intake["review_rejection_reference"] = "redacted-tally-review-rejection-1"
    intake["review_rejection_reasons"] = ["company_reference_not_approved"]
    intake["review_resubmission_reference"] = "redacted-tally-review-resubmission-1"

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
        "review_rejection_reason:company_reference_not_approved",
    ]


def test_tally_reviewed_evidence_intake_blocks_on_multiple_invalid_prior_review_cycles() -> None:
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
        "prior_review_cycle_count": 3,
        "total_review_cycle_count": 4,
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
        "prior_review_cycle:2:review_rejection_reference_missing",
        "prior_review_cycle:2:review_resubmission_reference_missing",
        "review_rejection_reason:company_scope_and_mapping_still_incomplete",
    ]
