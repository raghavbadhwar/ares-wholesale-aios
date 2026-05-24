"""Local proof packet helpers for sandbox-backed integration tests."""

from __future__ import annotations

import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

PROOF_COLLECTION_LIMITATION = (
    "Local proof collection packet only; it lists required artifact metadata and does not inspect files, secrets, or external systems."
)
EXTERNAL_EVIDENCE_BUNDLE_LIMITATION = (
    "Local external evidence bundle handoff packet only; it validates redacted metadata structure and does not inspect artifacts, secrets, or external systems."
)
REVIEWED_EVIDENCE_INTAKE_LIMITATION = (
    "Local reviewed external-evidence intake packet only; it replays redacted operator-login and filing-identity metadata without inspecting artifacts, secrets, or external systems."
)
PROOF_REVIEW_HANDOFF_LIMITATION = (
    "Local proof review handoff packet only; it routes redacted metadata for external review and does not inspect artifacts, secrets, or external systems."
)
PROOF_REVIEW_DECISION_LIMITATION = (
    "Local proof review decision packet only; it replays external metadata review decisions without inspecting artifacts, secrets, or external systems."
)
PROOF_REVIEW_ASSIGNMENT_LIMITATION = (
    "Local proof reviewer assignment packet only; it prepares specialized review routing without inspecting artifacts, secrets, or external systems."
)
PROOF_REVIEW_DECISION_LEDGER_LIMITATION = (
    "Local proof review decision ledger packet only; it replays persisted metadata review decisions without inspecting artifacts, secrets, or external systems."
)
PROOF_REVIEW_SIGNED_ENVELOPE_LIMITATION = (
    "Local proof review signed-envelope packet only; it validates signed review metadata and reviewer key registry snapshots without inspecting artifacts, secrets, or external systems."
)
PROOF_METADATA_ACCEPTED_STATUS = "metadata_accepted_for_review"
PROOF_METADATA_REJECTED_STATUS = "metadata_rejected"

_REQUIRED_ARTIFACTS = [
    {
        "artifact_id": "provider_sandbox_adapter_evidence",
        "category": "external_integrations",
        "required_for_feature_rows": [
            "GSTN API Integration",
            "UPI & Payment Gateway",
            "WhatsApp Business Integration",
            "Tally / Busy Sync",
        ],
        "required_for_done_state_gates": [
            "zero_gst_penalty_12_months",
            "ca_closes_books_without_reentry",
            "every_rupee_udhaar_settled",
        ],
        "required_metadata_fields": [
            "artifact_path_or_reference",
            "provider",
            "sandbox_or_production_like_tenant",
            "run_timestamp",
            "operator_or_accountant_reviewer",
            "redaction_confirmed",
        ],
        "metadata_validation_rules": [
            {
                "field": "redaction_confirmed",
                "type": "exact_true",
                "description": "must confirm the artifact metadata is redaction-safe",
            }
        ],
    },
    {
        "artifact_id": "owner_briefing_delivery_evidence",
        "category": "owner_briefing",
        "required_for_feature_rows": ["Daily Owner Briefing"],
        "required_for_done_state_gates": [
            "owner_trusts_agent_summaries",
            "reliable_7am_owner_briefing",
        ],
        "required_metadata_fields": [
            "delivery_period",
            "scheduled_delivery_time",
            "successful_delivery_count",
            "missed_delivery_count",
            "owner_acknowledgement_reference",
            "fallback_channel_used",
            "redaction_confirmed",
        ],
        "metadata_validation_rules": [
            {
                "field": "successful_delivery_count",
                "type": "minimum_integer",
                "minimum": 1,
                "description": "must show at least one delivered owner briefing",
            },
            {
                "field": "redaction_confirmed",
                "type": "exact_true",
                "description": "must confirm the artifact metadata is redaction-safe",
            },
        ],
    },
    {
        "artifact_id": "large_distributor_monthly_ops_evidence",
        "category": "monthly_operations",
        "required_for_feature_rows": [
            "GSTR-1 Auto-Preparation",
            "ITC Reconciliation (2A/2B)",
            "Beat Route Management",
            "Claim & Scheme Reconciliation",
            "Principal-wise P&L",
        ],
        "required_for_done_state_gates": ["large_distributor_monthly_compliance"],
        "required_metadata_fields": [
            "monthly_period",
            "sku_count",
            "principal_count",
            "gstr1_review_reference",
            "itc_review_reference",
            "claim_cycle_review_reference",
            "principal_pnl_review_reference",
            "accountant_or_owner_reviewer",
            "redaction_confirmed",
        ],
        "metadata_validation_rules": [
            {
                "field": "sku_count",
                "type": "minimum_integer",
                "minimum": 120,
                "description": "must cover at least 120 SKUs",
            },
            {
                "field": "principal_count",
                "type": "minimum_integer",
                "minimum": 8,
                "description": "must cover at least 8 principals",
            },
            {
                "field": "redaction_confirmed",
                "type": "exact_true",
                "description": "must confirm the artifact metadata is redaction-safe",
            },
        ],
    },
    {
        "artifact_id": "gst_12_month_outcome_evidence",
        "category": "longitudinal_compliance",
        "required_for_feature_rows": ["GSTN API Integration"],
        "required_for_done_state_gates": ["zero_gst_penalty_12_months"],
        "required_metadata_fields": [
            "compliance_period_start",
            "compliance_period_end",
            "penalty_count",
            "accountant_reviewer",
            "redaction_confirmed",
        ],
        "metadata_validation_rules": [
            {
                "field": "penalty_count",
                "type": "exact_integer",
                "expected": 0,
                "description": "must show zero GST penalties across the reviewed period",
            },
            {
                "start_field": "compliance_period_start",
                "end_field": "compliance_period_end",
                "type": "minimum_date_span_days",
                "minimum_days": 365,
                "description": "must cover at least 12 months of agent-managed GST operation",
            },
            {
                "field": "redaction_confirmed",
                "type": "exact_true",
                "description": "must confirm the artifact metadata is redaction-safe",
            },
        ],
    },
    {
        "artifact_id": "udhaar_settlement_evidence",
        "category": "collections_outcomes",
        "required_for_feature_rows": ["UPI Payment Reconciliation", "Collections Dashboard"],
        "required_for_done_state_gates": ["every_rupee_udhaar_settled"],
        "required_metadata_fields": [
            "pilot_period",
            "invoice_count",
            "settled_amount",
            "unsettled_amount",
            "bank_or_gateway_reconciliation_reference",
            "owner_or_accountant_reviewer",
            "redaction_confirmed",
        ],
        "metadata_validation_rules": [
            {
                "field": "invoice_count",
                "type": "minimum_integer",
                "minimum": 1,
                "description": "must cover at least one receivable invoice settlement",
            },
            {
                "field": "settled_amount",
                "type": "positive_decimal",
                "description": "must show a positive settled receivable amount",
            },
            {
                "field": "unsettled_amount",
                "type": "exact_decimal",
                "expected": "0.00",
                "description": "must show no remaining unsettled receivable amount",
            },
            {
                "field": "redaction_confirmed",
                "type": "exact_true",
                "description": "must confirm the artifact metadata is redaction-safe",
            },
        ],
    },
    {
        "artifact_id": "low_literacy_pilot_evidence",
        "category": "field_adoption",
        "required_for_feature_rows": ["Hinglish NLU Engine", "Regional Language Support"],
        "required_for_done_state_gates": ["small_wholesaler_no_training"],
        "required_metadata_fields": [
            "participant_role",
            "pilot_reference",
            "redaction_confirmed",
        ],
        "metadata_validation_rules": [
            {
                "field": "redaction_confirmed",
                "type": "exact_true",
                "description": "must confirm the artifact metadata is redaction-safe",
            }
        ],
    },
    {
        "artifact_id": "ca_close_without_reentry_evidence",
        "category": "accounting_close",
        "required_for_feature_rows": ["Tally / Busy Sync", "Principal-wise P&L"],
        "required_for_done_state_gates": ["ca_closes_books_without_reentry"],
        "required_metadata_fields": [
            "close_period",
            "tally_or_busy_reference",
            "ca_reviewer",
            "redaction_confirmed",
        ],
        "metadata_validation_rules": [
            {
                "field": "redaction_confirmed",
                "type": "exact_true",
                "description": "must confirm the artifact metadata is redaction-safe",
            }
        ],
    },
]

_ACCEPTED_METADATA_FIELDS = [
    "artifact_path_or_reference",
    "provider",
    "sandbox_or_production_like_tenant",
    "run_timestamp",
    "operator_or_accountant_reviewer",
    "redaction_confirmed",
]
_DONE_STATE_GATES = {
    "small_wholesaler_no_training": ["low_literacy_pilot_evidence"],
    "owner_trusts_agent_summaries": ["owner_briefing_delivery_evidence"],
    "ca_closes_books_without_reentry": [
        "provider_sandbox_adapter_evidence",
        "ca_close_without_reentry_evidence",
    ],
    "zero_gst_penalty_12_months": [
        "provider_sandbox_adapter_evidence",
        "gst_12_month_outcome_evidence",
    ],
    "every_rupee_udhaar_settled": [
        "provider_sandbox_adapter_evidence",
        "udhaar_settlement_evidence",
    ],
    "reliable_7am_owner_briefing": ["owner_briefing_delivery_evidence"],
}
_SOURCE_OF_TRUTH_GATE_LABELS = {
    "small_wholesaler_no_training": "Semi-literate salesman uses it daily without training",
    "owner_trusts_agent_summaries": "Owner trusts agent summaries without calling accountant",
    "ca_closes_books_without_reentry": "CA can close books from Tally without re-entry",
    "zero_gst_penalty_12_months": "Zero GST penalty across 12 months of agent-managed operation",
    "every_rupee_udhaar_settled": "Every rupee of udhaar is tracked to settlement",
    "reliable_7am_owner_briefing": "7 AM owner briefing reliably tells the owner what matters today",
}
_ARTIFACT_REVIEWER_ROLES = {
    "provider_sandbox_adapter_evidence": "operator_or_accountant_reviewer",
    "owner_briefing_delivery_evidence": "external_reviewer",
    "large_distributor_monthly_ops_evidence": "accountant_or_owner_reviewer",
    "gst_12_month_outcome_evidence": "accountant_reviewer",
    "udhaar_settlement_evidence": "owner_or_accountant_reviewer",
    "low_literacy_pilot_evidence": "observer",
    "ca_close_without_reentry_evidence": "ca_reviewer",
}
_SPECIALIZED_SUBAGENT_PROFILES = {
    "operator_or_accountant_reviewer": "integration_accounting_reviewer",
    "external_reviewer": "owner_operating_loop_reviewer",
    "accountant_or_owner_reviewer": "monthly_operations_reviewer",
    "accountant_reviewer": "gst_compliance_reviewer",
    "owner_or_accountant_reviewer": "collections_settlement_reviewer",
    "observer": "pilot_usability_observer",
    "ca_reviewer": "accounting_close_reviewer",
}
_DECISION_REQUIRED_FIELDS = [
    "artifact_id",
    "decision",
    "reviewer",
    "review_reference",
    "reviewed_at",
    "redaction_confirmed",
]


def build_benchmark_proof_collection_packet(
    *,
    provided_artifacts: list[dict[str, Any]] | None = None,
    metadata_manifest_files_read: bool = False,
) -> dict[str, Any]:
    """Build a deterministic local-only proof collection packet."""
    artifacts = provided_artifacts or []
    provided_by_id = {
        artifact.get("artifact_id"): artifact
        for artifact in artifacts
        if isinstance(artifact, dict) and artifact.get("artifact_id")
    }
    requirements: list[dict[str, Any]] = []
    accepted = 0
    rejected_artifacts: list[dict[str, Any]] = []
    for requirement in _REQUIRED_ARTIFACTS:
        artifact_id = requirement["artifact_id"]
        submitted = provided_by_id.get(artifact_id)
        rejection_reasons = (
            _validate_provided_metadata(requirement, submitted) if submitted is not None else []
        )
        if submitted is None:
            status = "missing"
            submitted_metadata = None
        elif rejection_reasons:
            status = PROOF_METADATA_REJECTED_STATUS
            submitted_metadata = None
            rejected_artifacts.append(
                {
                    "artifact_id": artifact_id,
                    "submitted_metadata": submitted,
                    "rejection_reasons": rejection_reasons,
                }
            )
        else:
            status = PROOF_METADATA_ACCEPTED_STATUS
            submitted_metadata = submitted
            accepted += 1
        requirements.append(
            {
                "artifact_id": artifact_id,
                "category": requirement["category"],
                "status": status,
                "proves_ship_ready": False,
                "required_for_feature_rows": list(requirement["required_for_feature_rows"]),
                "required_for_done_state_gates": list(requirement["required_for_done_state_gates"]),
                "required_metadata_fields": list(requirement["required_metadata_fields"]),
                "accepted_metadata_fields": list(_ACCEPTED_METADATA_FIELDS),
                "metadata_validation_rules": list(requirement["metadata_validation_rules"]),
                "submitted_metadata": submitted_metadata,
            }
        )
    total = len(requirements)
    done_state_gate_metadata_readiness = _build_done_state_gate_metadata_readiness(requirements)
    return {
        "mode": "local_proof_collection_packet",
        "status": "missing_external_evidence",
        "benchmark_parity": False,
        "ship_ready": False,
        "artifact_requirements_total": total,
        "artifact_requirements_accepted": accepted,
        "artifact_requirements_missing": total - accepted,
        "artifact_requirements_rejected": len(rejected_artifacts),
        "artifact_requirements": requirements,
        "artifact_statuses": {
            requirement["artifact_id"]: requirement["status"] for requirement in requirements
        },
        "rejected_artifacts": rejected_artifacts,
        "done_state_gate_metadata_summary": _summarize_done_state_gate_metadata_readiness(
            done_state_gate_metadata_readiness
        ),
        "done_state_gate_metadata_readiness": done_state_gate_metadata_readiness,
        "done_state_gate_statuses": {
            gate["gate"]: gate["status"] for gate in done_state_gate_metadata_readiness
        },
        "audit": {
            "metadata_manifest_files_read": metadata_manifest_files_read,
            "artifact_files_read": False,
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": PROOF_COLLECTION_LIMITATION,
        },
    }


def build_benchmark_external_evidence_bundle_packet(
    *,
    latest_local_test_result: str,
    evidence_bundles: list[dict[str, Any]] | None = None,
    external_evidence_bundle_files_read: bool = False,
    verify_reviewer_key_registry_snapshot_chain: bool = False,
) -> dict[str, Any]:
    """Build a deterministic local-only external evidence handoff packet."""
    bundles = evidence_bundles or []
    bundle_items = [
        _build_external_evidence_bundle_item(
            bundle,
            verify_reviewer_key_registry_snapshot_chain=verify_reviewer_key_registry_snapshot_chain,
        )
        for bundle in bundles
    ]
    accepted = sum(
        1 for bundle in bundle_items if bundle["bundle_status"] == "accepted_for_external_handoff"
    )
    return {
        "mode": "local_external_evidence_bundle_handoff_packet",
        "latest_local_test_result": latest_local_test_result,
        "benchmark_parity": False,
        "ship_ready": False,
        "external_evidence_bundle_summary": {
            "bundles_total": len(bundle_items),
            "bundles_accepted_for_handoff": accepted,
            "bundles_blocked": len(bundle_items) - accepted,
        },
        "external_evidence_bundles": bundle_items,
        "audit": {
            "external_evidence_bundle_files_read": external_evidence_bundle_files_read,
            "artifact_files_read": False,
            "secret_values_inspected": False,
            "live_api_called": False,
            "limitation": EXTERNAL_EVIDENCE_BUNDLE_LIMITATION,
        },
    }


def build_benchmark_reviewed_evidence_intake_packet(
    *,
    latest_local_test_result: str,
    reviewed_evidence_intakes: list[dict[str, Any]] | None = None,
    reviewed_evidence_intake_files_read: bool = False,
) -> dict[str, Any]:
    """Build a deterministic local-only reviewed external-evidence intake packet."""
    intakes = reviewed_evidence_intakes or []
    intake_items = [_build_reviewed_evidence_intake_item(intake) for intake in intakes]
    accepted = sum(
        1
        for item in intake_items
        if item["intake_status"] == "accepted_for_local_review_replay"
    )
    return {
        "mode": "local_reviewed_external_evidence_intake_packet",
        "latest_local_test_result": latest_local_test_result,
        "benchmark_parity": False,
        "ship_ready": False,
        "reviewed_evidence_intake_summary": {
            "intakes_total": len(intake_items),
            "intakes_accepted_for_local_replay": accepted,
            "intakes_blocked": len(intake_items) - accepted,
            "intakes_blocked_until_metadata_ready": sum(
                1 for item in intake_items if item["intake_status"] == "blocked_until_metadata_ready"
            ),
            "intakes_rejected_after_review": sum(
                1 for item in intake_items if item["intake_status"] == "blocked_after_review_rejection"
            ),
            "intakes_resubmitted_after_review_rejection": sum(
                1
                for item in intake_items
                if item["review_rejection_summary"]["reopened_after_review_rejection"]
            ),
            "intakes_with_multi_attempt_review_history": sum(
                1
                for item in intake_items
                if item["review_cycle_history_summary"]["prior_review_cycle_count"] > 0
            ),
            "intakes_with_operator_login_metadata": sum(
                1 for item in intake_items if item["operator_login_summary"]["metadata_ready"]
            ),
            "intakes_with_subject_metadata": sum(
                1 for item in intake_items if item["subject_metadata_summary"]["metadata_ready"]
            ),
        },
        "reviewed_evidence_intakes": intake_items,
        "audit": {
            "reviewed_evidence_intake_files_read": reviewed_evidence_intake_files_read,
            "artifact_files_read": False,
            "secret_values_inspected": False,
            "live_api_called": False,
            "limitation": REVIEWED_EVIDENCE_INTAKE_LIMITATION,
        },
    }


def build_benchmark_proof_review_handoff_packet(
    *,
    latest_local_test_result: str,
    provided_artifacts: list[dict[str, Any]] | None = None,
    metadata_manifest_files_read: bool = False,
) -> dict[str, Any]:
    """Build a deterministic local-only proof review handoff packet."""
    proof_packet = build_benchmark_proof_collection_packet(
        provided_artifacts=provided_artifacts,
        metadata_manifest_files_read=metadata_manifest_files_read,
    )
    artifact_review_queue = [
        _build_artifact_review_item(requirement)
        for requirement in proof_packet["artifact_requirements"]
    ]
    done_state_gate_review_queue = [
        _build_done_state_gate_review_item(gate)
        for gate in proof_packet["done_state_gate_metadata_readiness"]
    ]
    audit = dict(proof_packet["audit"])
    audit["limitation"] = PROOF_REVIEW_HANDOFF_LIMITATION
    return {
        "mode": "local_proof_review_handoff_packet",
        "review_scope": "metadata_review_only",
        "latest_local_test_result": latest_local_test_result,
        "benchmark_parity": False,
        "ship_ready": False,
        "artifact_review_summary": {
            "artifact_requirements_total": len(artifact_review_queue),
            "artifact_requirements_ready_for_external_review": sum(
                1 for item in artifact_review_queue if item["review_status"] == "pending_external_review"
            ),
            "artifact_requirements_missing_metadata": sum(
                1
                for item in artifact_review_queue
                if item["review_status"] == "blocked_until_metadata_submitted"
            ),
            "artifact_requirements_rejected_metadata": sum(
                1
                for item in artifact_review_queue
                if item["review_status"] == "blocked_until_valid_redacted_metadata"
            ),
            "artifact_requirements_proven": 0,
        },
        "artifact_review_queue": artifact_review_queue,
        "done_state_gate_review_summary": {
            "done_state_gates_total": len(done_state_gate_review_queue),
            "done_state_gates_pending_external_review": sum(
                1 for item in done_state_gate_review_queue if item["review_status"] == "pending_external_review"
            ),
            "done_state_gates_blocked_until_required_metadata_submitted": sum(
                1
                for item in done_state_gate_review_queue
                if item["review_status"] == "blocked_until_required_metadata_submitted"
            ),
            "done_state_gates_blocked_until_valid_redacted_metadata": sum(
                1
                for item in done_state_gate_review_queue
                if item["review_status"] == "blocked_until_valid_redacted_metadata"
            ),
            "done_state_gates_proven_by_review": 0,
        },
        "done_state_gate_review_queue": done_state_gate_review_queue,
        "proof_collection_packet": proof_packet,
        "audit": audit,
    }


def build_benchmark_proof_review_decision_packet(
    *,
    latest_local_test_result: str,
    provided_artifacts: list[dict[str, Any]] | None = None,
    review_decisions: list[dict[str, Any]] | None = None,
    metadata_manifest_files_read: bool = False,
) -> dict[str, Any]:
    """Replay deterministic external metadata review decisions without readiness claims."""
    handoff_packet = build_benchmark_proof_review_handoff_packet(
        latest_local_test_result=latest_local_test_result,
        provided_artifacts=provided_artifacts,
        metadata_manifest_files_read=metadata_manifest_files_read,
    )
    artifact_by_id = {
        item["artifact_id"]: item for item in handoff_packet["artifact_review_queue"]
    }
    decisions = [
        _build_review_decision_item(decision, artifact_by_id)
        for decision in (review_decisions or [])
    ]
    approved_by_artifact = {
        item["artifact_id"]
        for item in decisions
        if item["decision_status"] == "external_review_approved"
    }
    rejected_by_artifact = {
        item["artifact_id"]
        for item in decisions
        if item["decision_status"] == "external_review_rejected"
    }
    gate_review_decisions = [
        _build_done_state_gate_review_decision_item(gate, approved_by_artifact, rejected_by_artifact)
        for gate in handoff_packet["done_state_gate_review_queue"]
    ]
    audit = dict(handoff_packet["audit"])
    audit["limitation"] = PROOF_REVIEW_DECISION_LIMITATION
    return {
        "mode": "local_proof_review_decision_packet",
        "decision_scope": "external_metadata_review_decisions_only",
        "latest_local_test_result": latest_local_test_result,
        "benchmark_parity": False,
        "ship_ready": False,
        "artifact_review_decision_summary": {
            "review_decisions_total": len(decisions),
            "review_decisions_accepted": sum(
                1 for item in decisions if item["decision_status"] == "external_review_approved"
            ),
            "review_decisions_rejected": sum(
                1 for item in decisions if item["decision_status"] == "external_review_rejected"
            ),
            "review_decisions_blocked": sum(
                1 for item in decisions if item["decision_status"] == "external_review_blocked"
            ),
            "artifacts_approved_by_external_review": len(approved_by_artifact),
            "artifacts_rejected_by_external_review": len(rejected_by_artifact),
            "artifacts_proven": 0,
        },
        "artifact_review_decisions": decisions,
        "done_state_gate_review_decision_summary": {
            "done_state_gates_total": len(gate_review_decisions),
            "done_state_gates_with_external_review_complete_not_proven": sum(
                1
                for gate in gate_review_decisions
                if gate["review_decision_status"] == "external_review_complete_not_proven"
            ),
            "done_state_gates_blocked_until_review_complete": sum(
                1
                for gate in gate_review_decisions
                if gate["review_decision_status"] == "blocked_until_external_review_complete"
            ),
            "done_state_gates_proven_by_review": 0,
        },
        "done_state_gate_review_decisions": gate_review_decisions,
        "proof_review_handoff_packet": handoff_packet,
        "audit": audit,
    }


def build_benchmark_proof_reviewer_assignment_packet(
    *,
    latest_local_test_result: str,
    provided_artifacts: list[dict[str, Any]] | None = None,
    metadata_manifest_files_read: bool = False,
) -> dict[str, Any]:
    """Build deterministic specialized reviewer assignments for local proof metadata."""
    handoff_packet = build_benchmark_proof_review_handoff_packet(
        latest_local_test_result=latest_local_test_result,
        provided_artifacts=provided_artifacts,
        metadata_manifest_files_read=metadata_manifest_files_read,
    )
    assignments = [
        _build_reviewer_assignment_item(item) for item in handoff_packet["artifact_review_queue"]
    ]
    audit = dict(handoff_packet["audit"])
    audit["limitation"] = PROOF_REVIEW_ASSIGNMENT_LIMITATION
    return {
        "mode": "local_proof_reviewer_assignment_packet",
        "assignment_scope": "specialized_external_metadata_review_assignments_only",
        "latest_local_test_result": latest_local_test_result,
        "benchmark_parity": False,
        "ship_ready": False,
        "reviewer_assignment_summary": {
            "artifact_requirements_total": len(assignments),
            "assignments_ready_for_specialized_review": sum(
                1 for item in assignments if item["assignment_status"] == "ready_for_specialized_review"
            ),
            "assignments_blocked_until_metadata_ready": sum(
                1 for item in assignments if item["assignment_status"] != "ready_for_specialized_review"
            ),
            "artifacts_proven_by_assignment": 0,
        },
        "reviewer_assignments": assignments,
        "proof_review_handoff_packet": handoff_packet,
        "audit": audit,
    }


def build_benchmark_proof_review_decision_ledger_packet(
    *,
    latest_local_test_result: str,
    provided_artifacts: list[dict[str, Any]] | None = None,
    review_decision_ledger_entries: list[dict[str, Any]] | None = None,
    metadata_manifest_files_read: bool = False,
    decision_ledger_files_read: bool = False,
) -> dict[str, Any]:
    """Replay persisted metadata review decisions through a deterministic local ledger surface."""
    ledger_entries = review_decision_ledger_entries or []
    replayable_decisions = [
        entry["decision"]
        for entry in ledger_entries
        if _ledger_entry_shape_rejection_reasons(entry) == []
    ]
    replayed_packet = build_benchmark_proof_review_decision_packet(
        latest_local_test_result=latest_local_test_result,
        provided_artifacts=provided_artifacts,
        review_decisions=replayable_decisions,
        metadata_manifest_files_read=metadata_manifest_files_read,
    )
    decision_by_artifact = {
        item["artifact_id"]: item for item in replayed_packet["artifact_review_decisions"]
    }
    replay_items = [
        _build_review_decision_ledger_item(entry, decision_by_artifact)
        for entry in ledger_entries
    ]
    audit = dict(replayed_packet["audit"])
    audit["decision_ledger_files_read"] = decision_ledger_files_read
    audit["limitation"] = PROOF_REVIEW_DECISION_LEDGER_LIMITATION
    return {
        "mode": "local_proof_review_decision_ledger_packet",
        "ledger_scope": "persisted_external_metadata_review_decision_replay_only",
        "latest_local_test_result": latest_local_test_result,
        "benchmark_parity": False,
        "ship_ready": False,
        "review_decision_ledger_summary": {
            "ledger_entries_total": len(replay_items),
            "ledger_entries_replayed": sum(1 for item in replay_items if item["replay_status"] == "replayed"),
            "ledger_entries_blocked": sum(1 for item in replay_items if item["replay_status"] == "blocked"),
            "ledger_entries_with_approved_decisions": sum(
                1 for item in replay_items if item["decision_status"] == "external_review_approved"
            ),
            "ledger_entries_with_rejected_decisions": sum(
                1 for item in replay_items if item["decision_status"] == "external_review_rejected"
            ),
            "artifacts_proven_by_ledger": 0,
        },
        "review_decision_ledger_entries": replay_items,
        "replayed_review_decision_packet": replayed_packet,
        "audit": audit,
    }


def build_benchmark_proof_review_signed_envelope_packet(
    *,
    latest_local_test_result: str,
    provided_artifacts: list[dict[str, Any]] | None = None,
    signed_review_envelopes: list[dict[str, Any]] | None = None,
    reviewer_key_registry: list[dict[str, Any]] | None = None,
    reviewer_key_registry_snapshots: list[dict[str, Any]] | None = None,
    metadata_manifest_files_read: bool = False,
    signed_envelope_files_read: bool = False,
    reviewer_key_registry_files_read: bool = False,
    reviewer_key_registry_snapshot_files_read: bool = False,
    verify_reviewer_key_registry_snapshot_chain: bool = False,
) -> dict[str, Any]:
    """Validate signed proof-review metadata and reviewer-key registry state locally."""
    envelopes = signed_review_envelopes or []
    key_registry_snapshots = reviewer_key_registry_snapshots or []
    snapshot_rejection_reasons = _reviewer_key_registry_snapshot_rejection_reasons(
        key_registry_snapshots,
        verify_snapshot_chain=verify_reviewer_key_registry_snapshot_chain,
    )
    active_snapshot = _latest_verified_reviewer_key_registry_snapshot(
        key_registry_snapshots,
        snapshot_rejection_reasons,
    )
    key_registry = (
        reviewer_key_registry
        or (active_snapshot.get("reviewer_keys") if active_snapshot else None)
        or []
    )
    key_registry_rejection_reasons = _signed_envelope_key_registry_rejection_reasons(
        envelopes,
        key_registry,
    )
    if key_registry_snapshots and active_snapshot is None:
        key_registry_rejection_reasons = {
            index: reasons + ["reviewer_key_registry_snapshot_chain_unverified"]
            for index, reasons in (
                (index, list(key_registry_rejection_reasons.get(index, [])))
                for index in range(len(envelopes))
            )
        }
    handoff_packet = build_benchmark_proof_review_handoff_packet(
        latest_local_test_result=latest_local_test_result,
        provided_artifacts=provided_artifacts,
        metadata_manifest_files_read=metadata_manifest_files_read,
    )
    replayable_decisions = [
        envelope["decision"]
        for index, envelope in enumerate(envelopes)
        if not _signed_review_envelope_shape_rejection_reasons(envelope)
        and not key_registry_rejection_reasons.get(index, [])
    ]
    replayed_packet = build_benchmark_proof_review_decision_packet(
        latest_local_test_result=latest_local_test_result,
        provided_artifacts=provided_artifacts,
        review_decisions=replayable_decisions,
        metadata_manifest_files_read=metadata_manifest_files_read,
    )
    signed_envelope_items = _build_signed_review_envelopes(
        envelopes,
        replayed_packet["artifact_review_decisions"],
        handoff_packet["artifact_review_queue"],
        key_registry_rejection_reasons,
        enforce_key_registry=bool(key_registry) or bool(key_registry_snapshots),
        active_registry_snapshot=active_snapshot,
    )
    audit = dict(replayed_packet["audit"])
    audit["signed_envelope_files_read"] = signed_envelope_files_read
    audit["reviewer_key_registry_files_read"] = reviewer_key_registry_files_read
    audit["reviewer_key_registry_snapshot_files_read"] = (
        reviewer_key_registry_snapshot_files_read
    )
    audit["reviewer_key_registry_snapshot_chain_verified"] = (
        _summarize_reviewer_key_registry_snapshots(
            key_registry_snapshots,
            snapshot_rejection_reasons,
            verify_snapshot_chain=verify_reviewer_key_registry_snapshot_chain,
        )["registry_snapshots_verified"]
        == len(key_registry_snapshots)
        if verify_reviewer_key_registry_snapshot_chain and key_registry_snapshots
        else False
    )
    audit["limitation"] = PROOF_REVIEW_SIGNED_ENVELOPE_LIMITATION
    return {
        "mode": "local_proof_review_signed_envelope_packet",
        "signature_scope": "signed_external_metadata_review_decision_envelopes_only",
        "latest_local_test_result": latest_local_test_result,
        "benchmark_parity": False,
        "ship_ready": False,
        "signed_envelope_summary": _summarize_signed_review_envelopes(
            signed_envelope_items
        ),
        "reviewer_key_registry_summary": _summarize_reviewer_key_registry(
            key_registry,
            signed_envelope_items,
        ),
        "reviewer_key_registry_snapshot_summary": _summarize_reviewer_key_registry_snapshots(
            key_registry_snapshots,
            snapshot_rejection_reasons,
            verify_snapshot_chain=verify_reviewer_key_registry_snapshot_chain,
        ),
        "signed_review_envelopes": signed_envelope_items,
        "replayed_review_decision_packet": replayed_packet,
        "proof_review_handoff_packet": handoff_packet,
        "audit": audit,
    }


def _build_external_evidence_bundle_item(
    bundle: dict[str, Any],
    *,
    verify_reviewer_key_registry_snapshot_chain: bool,
) -> dict[str, Any]:
    artifacts = bundle.get("artifacts") if isinstance(bundle.get("artifacts"), list) else []
    review_decisions = (
        bundle.get("review_decisions") if isinstance(bundle.get("review_decisions"), list) else []
    )
    signed_envelopes = (
        bundle.get("signed_envelopes") if isinstance(bundle.get("signed_envelopes"), list) else []
    )
    registry_snapshots = (
        bundle.get("reviewer_key_registry_snapshots")
        if isinstance(bundle.get("reviewer_key_registry_snapshots"), list)
        else []
    )
    proof_packet = build_benchmark_proof_collection_packet(provided_artifacts=artifacts)
    snapshot_rejection_reasons = _reviewer_key_registry_snapshot_rejection_reasons(
        registry_snapshots,
        verify_snapshot_chain=verify_reviewer_key_registry_snapshot_chain,
    )
    snapshot_summary = _summarize_reviewer_key_registry_snapshots(
        registry_snapshots,
        snapshot_rejection_reasons,
        verify_snapshot_chain=verify_reviewer_key_registry_snapshot_chain,
    )
    review_decisions_accepted = sum(
        1 for decision in review_decisions if decision.get("decision") == "approved"
    )
    signed_envelopes_accepted = sum(
        1
        for envelope in signed_envelopes
        if envelope.get("signature_reference") and envelope.get("signer_key_reference")
    )
    registry_snapshots_verified = snapshot_summary["registry_snapshots_verified"]
    accepted = (
        bool(bundle.get("redaction_confirmed"))
        and proof_packet["artifact_requirements_accepted"] > 0
        and proof_packet["artifact_requirements_rejected"] == 0
        and review_decisions_accepted > 0
        and signed_envelopes_accepted > 0
        and registry_snapshots_verified > 0
    )
    return {
        "bundle_id": bundle.get("bundle_id"),
        "bundle_status": (
            "accepted_for_external_handoff" if accepted else "blocked_until_metadata_ready"
        ),
        "proof_collection_summary": {
            "artifact_requirements_total": proof_packet["artifact_requirements_total"],
            "artifact_requirements_accepted": proof_packet["artifact_requirements_accepted"],
            "artifact_requirements_missing": proof_packet["artifact_requirements_missing"],
            "artifact_requirements_rejected": proof_packet["artifact_requirements_rejected"],
        },
        "review_decision_summary": {
            "review_decisions_total": len(review_decisions),
            "review_decisions_accepted": review_decisions_accepted,
        },
        "signed_envelope_summary": {
            "signed_envelopes_total": len(signed_envelopes),
            "signed_envelopes_accepted": signed_envelopes_accepted,
        },
        "reviewer_key_registry_snapshot_summary": {
            "registry_snapshots_total": len(registry_snapshots),
            "registry_snapshots_verified": registry_snapshots_verified,
        },
    }


def _build_reviewed_evidence_intake_item(intake: dict[str, Any]) -> dict[str, Any]:
    metadata_rejection_reasons = _reviewed_evidence_intake_metadata_rejection_reasons(intake)
    review_cycle_history_state = _reviewed_evidence_intake_review_cycle_history_state(intake)
    review_outcome_state = _reviewed_evidence_intake_review_outcome_state(intake)
    rejection_reasons = (
        metadata_rejection_reasons
        + review_cycle_history_state["rejection_reasons"]
        + review_outcome_state["rejection_reasons"]
    )
    operator_login = intake.get("operator_login_metadata")
    operator_login_mapping = operator_login if isinstance(operator_login, dict) else {}
    subject_kind, subject_metadata_mapping = _resolve_review_subject_metadata(intake)
    if metadata_rejection_reasons or review_cycle_history_state["rejection_reasons"]:
        intake_status = "blocked_until_metadata_ready"
    elif review_outcome_state["status"] == "review_rejected":
        intake_status = "blocked_after_review_rejection"
    elif review_outcome_state["status"] == "ready_for_local_review_replay":
        intake_status = "accepted_for_local_review_replay"
    else:
        intake_status = "blocked_until_metadata_ready"
    item = {
        "intake_id": intake.get("intake_id"),
        "bundle_id": intake.get("bundle_id"),
        "artifact_id": intake.get("artifact_id"),
        "provider": intake.get("provider"),
        "intake_status": intake_status,
        "review_outcome": intake.get("review_outcome"),
        "review_scope": intake.get("review_scope"),
        "operator_login_summary": {
            "actor_role": operator_login_mapping.get("actor_role"),
            "login_surface": operator_login_mapping.get("login_surface"),
            "session_reference_present": bool(
                str(operator_login_mapping.get("session_reference") or "").strip()
            ),
            "metadata_ready": not any(
                reason.startswith("operator_login_metadata.")
                for reason in rejection_reasons
            ),
        },
        "subject_metadata_summary": {
            "subject_metadata_kind": subject_kind,
            "subject_identifier": _subject_metadata_identifier(subject_metadata_mapping),
            "subject_scope": _subject_metadata_scope(subject_metadata_mapping),
            "operation": subject_metadata_mapping.get("operation"),
            "portal_reference_present": bool(
                str(subject_metadata_mapping.get("portal_reference") or "").strip()
            ),
            "metadata_ready": not any(
                reason.startswith("subject_metadata.")
                for reason in rejection_reasons
            ),
        },
        "review_rejection_summary": review_outcome_state["summary"],
        "review_cycle_history_summary": review_cycle_history_state["summary"],
        "rejection_reasons": rejection_reasons,
    }
    if subject_kind == "gst_filing_identity":
        item["filing_identity_summary"] = item["subject_metadata_summary"]
    return item


def _reviewed_evidence_intake_metadata_rejection_reasons(intake: dict[str, Any]) -> list[str]:
    if not isinstance(intake, dict):
        return ["invalid_reviewed_evidence_intake_payload"]
    reasons: list[str] = []
    for field in (
        "intake_id",
        "bundle_id",
        "transcript_id",
        "artifact_id",
        "provider",
        "reviewed_at",
        "reviewer_reference",
        "review_scope",
    ):
        if not str(intake.get(field) or "").strip():
            reasons.append(f"missing_intake_field:{field}")
    if intake.get("artifact_id") != "provider_sandbox_adapter_evidence":
        reasons.append("unsupported_artifact_id")
    if intake.get("review_scope") != "reviewed_external_evidence_intake_only":
        reasons.append("invalid_review_scope")
    if intake.get("redaction_confirmed") is not True:
        reasons.append("redaction_not_confirmed")
    reasons.extend(
        _required_nested_metadata_rejection_reasons(
            intake.get("operator_login_metadata"),
            field_name="operator_login_metadata",
            required_fields=("actor_role", "login_reference", "session_reference", "login_surface"),
        )
    )
    reasons.extend(
        _review_subject_metadata_rejection_reasons(intake)
    )
    return reasons


def _reviewed_evidence_intake_review_outcome_state(intake: dict[str, Any]) -> dict[str, Any]:
    outcome = str(intake.get("review_outcome") or "").strip()
    if outcome == "metadata_review_complete_not_verified":
        return {
            "status": "ready_for_local_review_replay",
            "rejection_reasons": [],
            "summary": {
                "rejected_after_review": False,
                "review_rejection_reference_present": False,
                "review_rejection_reason_count": 0,
                "reopened_after_review_rejection": False,
                "review_resubmission_reference_present": False,
            },
        }
    if outcome == "metadata_review_rejected":
        review_rejection_reference = str(intake.get("review_rejection_reference") or "").strip()
        review_resubmission_reference = str(
            intake.get("review_resubmission_reference") or ""
        ).strip()
        raw_reasons = intake.get("review_rejection_reasons")
        normalized_reasons = [
            str(reason).strip()
            for reason in raw_reasons
            if str(reason).strip()
        ] if isinstance(raw_reasons, list) else []
        missing_reference = not review_rejection_reference
        missing_reasons = not normalized_reasons
        rejection_reasons = [
            *(["review_rejection_reference_missing"] if missing_reference else []),
            *(["review_rejection_reasons_missing"] if missing_reasons else []),
            *[f"review_rejection_reason:{reason}" for reason in normalized_reasons],
        ]
        return {
            "status": (
                "invalid_review_rejection_payload"
                if missing_reference or missing_reasons
                else "review_rejected"
            ),
            "rejection_reasons": rejection_reasons,
            "summary": {
                "rejected_after_review": True,
                "review_rejection_reference_present": bool(review_rejection_reference),
                "review_rejection_reason_count": len(normalized_reasons),
                "reopened_after_review_rejection": bool(review_resubmission_reference),
                "review_resubmission_reference_present": bool(
                    review_resubmission_reference
                ),
            },
        }
    if outcome == "metadata_review_resubmitted_after_rejection":
        review_rejection_reference = str(intake.get("review_rejection_reference") or "").strip()
        review_resubmission_reference = str(
            intake.get("review_resubmission_reference") or ""
        ).strip()
        raw_reasons = intake.get("review_rejection_reasons")
        normalized_reasons = [
            str(reason).strip()
            for reason in raw_reasons
            if str(reason).strip()
        ] if isinstance(raw_reasons, list) else []
        missing_reference = not review_rejection_reference
        missing_reasons = not normalized_reasons
        missing_resubmission_reference = not review_resubmission_reference
        rejection_reasons = [
            *(["review_rejection_reference_missing"] if missing_reference else []),
            *(["review_rejection_reasons_missing"] if missing_reasons else []),
            *(
                ["review_resubmission_reference_missing"]
                if missing_resubmission_reference
                else []
            ),
            *[f"review_rejection_reason:{reason}" for reason in normalized_reasons],
        ]
        return {
            "status": (
                "invalid_review_resubmission_payload"
                if missing_reference or missing_reasons or missing_resubmission_reference
                else "ready_for_local_review_replay"
            ),
            "rejection_reasons": rejection_reasons,
            "summary": {
                "rejected_after_review": False,
                "review_rejection_reference_present": bool(review_rejection_reference),
                "review_rejection_reason_count": len(normalized_reasons),
                "reopened_after_review_rejection": True,
                "review_resubmission_reference_present": bool(
                    review_resubmission_reference
                ),
            },
        }
    return {
        "status": "invalid_review_outcome",
        "rejection_reasons": ["invalid_review_outcome"],
        "summary": {
            "rejected_after_review": False,
            "review_rejection_reference_present": False,
            "review_rejection_reason_count": 0,
            "reopened_after_review_rejection": False,
            "review_resubmission_reference_present": False,
        },
    }


def _reviewed_evidence_intake_review_cycle_history_state(
    intake: dict[str, Any],
) -> dict[str, Any]:
    raw_cycles = intake.get("prior_review_cycles")
    if raw_cycles is None:
        raw_cycles = []
    if not isinstance(raw_cycles, list):
        return {
            "rejection_reasons": ["prior_review_cycles_invalid"],
            "summary": {
                "prior_review_cycle_count": 0,
                "total_review_cycle_count": 1,
                "all_prior_cycles_complete": False,
                "multi_attempt_review_replay": False,
            },
        }

    rejection_reasons: list[str] = []
    completed_cycles = 0
    for index, cycle in enumerate(raw_cycles):
        prefix = f"prior_review_cycle:{index}"
        if not isinstance(cycle, dict):
            rejection_reasons.append(f"{prefix}:invalid_payload")
            continue
        review_rejection_reference = str(cycle.get("review_rejection_reference") or "").strip()
        raw_reasons = cycle.get("review_rejection_reasons")
        normalized_reasons = [
            str(reason).strip()
            for reason in raw_reasons
            if str(reason).strip()
        ] if isinstance(raw_reasons, list) else []
        review_resubmission_reference = str(
            cycle.get("review_resubmission_reference") or ""
        ).strip()
        if not review_rejection_reference:
            rejection_reasons.append(f"{prefix}:review_rejection_reference_missing")
        if not normalized_reasons:
            rejection_reasons.append(f"{prefix}:review_rejection_reasons_missing")
        if not review_resubmission_reference:
            rejection_reasons.append(f"{prefix}:review_resubmission_reference_missing")
        if (
            review_rejection_reference
            and normalized_reasons
            and review_resubmission_reference
        ):
            completed_cycles += 1

    prior_review_cycle_count = len(raw_cycles)
    return {
        "rejection_reasons": rejection_reasons,
        "summary": {
            "prior_review_cycle_count": prior_review_cycle_count,
            "total_review_cycle_count": prior_review_cycle_count + 1,
            "all_prior_cycles_complete": completed_cycles == prior_review_cycle_count,
            "multi_attempt_review_replay": prior_review_cycle_count > 0,
        },
    }


def _resolve_review_subject_metadata(intake: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    subject_metadata = intake.get("subject_metadata")
    if isinstance(subject_metadata, dict):
        return (
            str(intake.get("subject_metadata_kind") or "").strip() or "generic_subject_identity",
            subject_metadata,
        )
    filing_identity = intake.get("filing_identity_metadata")
    if isinstance(filing_identity, dict):
        return ("gst_filing_identity", filing_identity)
    return ("", {})


def _review_subject_metadata_rejection_reasons(intake: dict[str, Any]) -> list[str]:
    subject_kind, metadata = _resolve_review_subject_metadata(intake)
    if not subject_kind:
        return ["missing_intake_field:subject_metadata_kind", "subject_metadata.invalid_payload"]
    reasons = _required_nested_metadata_rejection_reasons(
        metadata,
        field_name="subject_metadata",
        required_fields=("operation", "portal_reference"),
    )
    if not _subject_metadata_identifier(metadata):
        reasons.append("subject_metadata.missing_identifier")
    if not _subject_metadata_scope(metadata):
        reasons.append("subject_metadata.missing_scope")
    return reasons


def _subject_metadata_identifier(metadata: dict[str, Any]) -> str:
    for key in (
        "gstin",
        "subject_reference",
        "merchant_reference",
        "message_reference",
        "company_reference",
    ):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _subject_metadata_scope(metadata: dict[str, Any]) -> str:
    for key in (
        "filing_period",
        "subject_scope",
        "settlement_window",
        "conversation_window",
        "bridge_mode",
    ):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return ""


def _required_nested_metadata_rejection_reasons(
    metadata: Any,
    *,
    field_name: str,
    required_fields: tuple[str, ...],
) -> list[str]:
    if not isinstance(metadata, dict):
        return [f"{field_name}.invalid_payload"]
    reasons: list[str] = []
    for nested_field in required_fields:
        if not str(metadata.get(nested_field) or "").strip():
            reasons.append(f"{field_name}.missing_field:{nested_field}")
    if metadata.get("redaction_confirmed") is not True:
        reasons.append(f"{field_name}.redaction_not_confirmed")
    return reasons


def _build_artifact_review_item(requirement: dict[str, Any]) -> dict[str, Any]:
    artifact_id = requirement["artifact_id"]
    metadata_status = requirement["status"]
    if metadata_status == PROOF_METADATA_ACCEPTED_STATUS:
        review_status = "pending_external_review"
    elif metadata_status == PROOF_METADATA_REJECTED_STATUS:
        review_status = "blocked_until_valid_redacted_metadata"
    else:
        review_status = "blocked_until_metadata_submitted"
    return {
        "artifact_id": artifact_id,
        "category": requirement["category"],
        "metadata_status": metadata_status,
        "review_status": review_status,
        "required_reviewer": _ARTIFACT_REVIEWER_ROLES[artifact_id],
        "required_for_done_state_gates": list(requirement["required_for_done_state_gates"]),
        "source_of_truth_gates": [
            _SOURCE_OF_TRUTH_GATE_LABELS[gate]
            for gate in requirement["required_for_done_state_gates"]
            if gate in _SOURCE_OF_TRUTH_GATE_LABELS
        ],
        "required_actions": [
            "verify redaction quality outside Ares",
            "verify artifact authenticity outside Ares",
            "confirm no forbidden content is present",
            "attach external reviewer decision before any readiness claim",
        ],
        "proves_artifact_requirement": False,
    }


def _build_done_state_gate_review_item(gate: dict[str, Any]) -> dict[str, Any]:
    metadata_status = gate["status"]
    if metadata_status == "metadata_submitted_for_review":
        review_status = "pending_external_review"
    elif metadata_status == "metadata_rejected":
        review_status = "blocked_until_valid_redacted_metadata"
    else:
        review_status = "blocked_until_required_metadata_submitted"
    return {
        "gate": gate["gate"],
        "source_of_truth_gate": _SOURCE_OF_TRUTH_GATE_LABELS[gate["gate"]],
        "metadata_status": metadata_status,
        "review_status": review_status,
        "accepted_artifact_ids": list(gate["accepted_artifact_ids"]),
        "missing_artifact_ids": list(gate["missing_artifact_ids"]),
        "rejected_artifact_ids": list(gate["rejected_artifact_ids"]),
        "proves_done_state_gate": False,
    }


def _build_review_decision_item(
    decision: dict[str, Any],
    artifact_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(decision, dict):
        return {
            "artifact_id": "",
            "decision_status": "external_review_blocked",
            "decision": "",
            "reviewer": "",
            "review_reference": "",
            "reviewed_at": "",
            "rejection_reasons": ["invalid_decision_payload"],
            "proves_artifact_requirement": False,
        }
    artifact_id = str(decision.get("artifact_id", ""))
    artifact = artifact_by_id.get(artifact_id)
    rejection_reasons: list[str] = []
    if artifact is None or artifact["review_status"] != "pending_external_review":
        rejection_reasons.append("artifact_not_ready_for_external_review")
    expected_reviewer = _ARTIFACT_REVIEWER_ROLES.get(artifact_id)
    if expected_reviewer is not None and decision.get("reviewer") != expected_reviewer:
        rejection_reasons.append(f"reviewer_mismatch: expected {expected_reviewer}")
    if decision.get("redaction_confirmed") is not True:
        rejection_reasons.append("redaction_review_not_confirmed")
    decision_value = decision.get("decision")
    if decision_value not in {"approved", "rejected"}:
        rejection_reasons.append("invalid_decision_value")
    if rejection_reasons:
        decision_status = "external_review_blocked"
    elif decision_value == "approved":
        decision_status = "external_review_approved"
    else:
        decision_status = "external_review_rejected"
    return {
        "artifact_id": artifact_id,
        "decision_status": decision_status,
        "decision": decision_value,
        "reviewer": decision.get("reviewer", ""),
        "review_reference": decision.get("review_reference", ""),
        "reviewed_at": decision.get("reviewed_at", ""),
        "rejection_reasons": rejection_reasons,
        "proves_artifact_requirement": False,
    }


def _build_done_state_gate_review_decision_item(
    gate: dict[str, Any],
    approved_by_artifact: set[str],
    rejected_by_artifact: set[str],
) -> dict[str, Any]:
    required_ids = _DONE_STATE_GATES[gate["gate"]]
    approved = [artifact_id for artifact_id in required_ids if artifact_id in approved_by_artifact]
    rejected = [artifact_id for artifact_id in required_ids if artifact_id in rejected_by_artifact]
    missing = [
        artifact_id
        for artifact_id in required_ids
        if artifact_id not in approved_by_artifact and artifact_id not in rejected_by_artifact
    ]
    status = (
        "external_review_complete_not_proven"
        if approved and not missing and not rejected
        else "blocked_until_external_review_complete"
    )
    return {
        "gate": gate["gate"],
        "review_decision_status": status,
        "approved_artifact_ids": approved,
        "rejected_artifact_ids": rejected,
        "missing_review_decision_artifact_ids": missing,
        "proves_done_state_gate": False,
    }


def _build_reviewer_assignment_item(artifact_review_item: dict[str, Any]) -> dict[str, Any]:
    reviewer_role = artifact_review_item["required_reviewer"]
    ready = artifact_review_item["review_status"] == "pending_external_review"
    return {
        "artifact_id": artifact_review_item["artifact_id"],
        "required_for_done_state_gates": list(artifact_review_item["required_for_done_state_gates"]),
        "source_of_truth_gates": list(artifact_review_item["source_of_truth_gates"]),
        "assignment_status": (
            "ready_for_specialized_review" if ready else "blocked_until_metadata_ready"
        ),
        "reviewer_role": reviewer_role,
        "specialized_subagent_profile": _SPECIALIZED_SUBAGENT_PROFILES[reviewer_role],
        "decision_contract": {
            "required_fields": list(_DECISION_REQUIRED_FIELDS),
            "allowed_decisions": ["approved", "rejected"],
            "accepted_reviewer": reviewer_role,
            "proves_artifact_requirement": False,
        },
        "local_execution_constraints": {
            "metadata_only": True,
            "artifact_files_read": False,
            "secret_values_inspected": False,
            "live_api_called": False,
        },
        "blocked_reason": "" if ready else artifact_review_item["review_status"],
    }


def _ledger_entry_shape_rejection_reasons(entry: dict[str, Any]) -> list[str]:
    if not isinstance(entry, dict):
        return ["invalid_ledger_entry_payload"]
    missing_fields = [
        field for field in ("ledger_entry_id", "recorded_at", "decision") if field not in entry
    ]
    reasons: list[str] = []
    if missing_fields:
        reasons.append(f"missing_ledger_entry_fields: {', '.join(sorted(missing_fields))}")
    if "decision" in entry and not isinstance(entry["decision"], dict):
        reasons.append("invalid_decision_payload")
    return reasons


def _build_review_decision_ledger_item(
    entry: dict[str, Any],
    decision_by_artifact: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    reasons = _ledger_entry_shape_rejection_reasons(entry)
    if not isinstance(entry, dict):
        return {
            "ledger_entry_id": "",
            "recorded_at": "",
            "replay_status": "blocked",
            "artifact_id": "",
            "decision_status": "external_review_blocked",
            "rejection_reasons": reasons,
            "proves_artifact_requirement": False,
        }
    decision_payload = entry.get("decision")
    artifact_id = decision_payload.get("artifact_id", "") if isinstance(decision_payload, dict) else ""
    decision_item = decision_by_artifact.get(artifact_id)
    if decision_item is None and "invalid_decision_payload" not in reasons:
        reasons.append("artifact_not_ready_for_external_review")
    if decision_item is not None and decision_item["decision_status"] == "external_review_blocked":
        reasons.extend(
            reason
            for reason in decision_item["rejection_reasons"]
            if reason not in reasons
        )
    blocked = bool(reasons)
    return {
        "ledger_entry_id": entry.get("ledger_entry_id", ""),
        "recorded_at": entry.get("recorded_at", ""),
        "replay_status": "blocked" if blocked else "replayed",
        "artifact_id": artifact_id,
        "decision_status": (
            "external_review_blocked"
            if blocked
            else decision_item["decision_status"]
        ),
        "rejection_reasons": reasons,
        "proves_artifact_requirement": False,
    }


def _build_signed_review_envelopes(
    envelopes: list[dict[str, Any]],
    decision_statuses: list[dict[str, Any]],
    artifact_review_queue: list[dict[str, Any]],
    key_registry_rejection_reasons: dict[int, list[str]],
    *,
    enforce_key_registry: bool,
    active_registry_snapshot: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    replayed_statuses_iter = iter(decision_statuses)
    review_items_by_id = {item["artifact_id"]: item for item in artifact_review_queue}
    signed_envelope_items: list[dict[str, Any]] = []
    for index, envelope in enumerate(envelopes):
        shape_rejection_reasons = _signed_review_envelope_shape_rejection_reasons(envelope)
        key_rejection_reasons = key_registry_rejection_reasons.get(index, [])
        if shape_rejection_reasons or key_rejection_reasons:
            decision = envelope.get("decision")
            artifact_id = decision.get("artifact_id") if isinstance(decision, dict) else ""
            decision_item = (
                _build_review_decision_item(
                    decision,
                    review_items_by_id,
                )
                if isinstance(decision, dict)
                else None
            )
            decision_rejection_reasons = (
                list(decision_item["rejection_reasons"]) if decision_item is not None else []
            )
            signed_envelope_items.append(
                {
                    "envelope_id": str(envelope.get("envelope_id") or ""),
                    "signature_status": "signature_metadata_blocked",
                    "artifact_id": artifact_id,
                    "decision_status": "external_review_blocked",
                    "reviewer": decision.get("reviewer") if isinstance(decision, dict) else None,
                    "signature_scheme": envelope.get("signature_scheme"),
                    "signer_key_reference": envelope.get("signer_key_reference"),
                    "signature_reference": envelope.get("signature_reference"),
                    "signed_at": envelope.get("signed_at"),
                    "rejection_reasons": shape_rejection_reasons
                    + key_rejection_reasons
                    + decision_rejection_reasons,
                    "proves_artifact_requirement": False,
                }
            )
            if enforce_key_registry:
                signed_envelope_items[-1]["key_registry_status"] = (
                    "blocked_reviewer_key"
                    if key_rejection_reasons
                    else "allowed_reviewer_key"
                )
                _attach_reviewer_key_registry_snapshot(
                    signed_envelope_items[-1],
                    active_registry_snapshot,
                    key_rejection_reasons,
                )
            continue

        decision_status = next(replayed_statuses_iter)
        blocked = decision_status["decision_status"] == "external_review_blocked"
        signed_envelope_items.append(
            {
                "envelope_id": str(envelope["envelope_id"]),
                "signature_status": (
                    "signature_metadata_blocked"
                    if blocked
                    else "signature_metadata_accepted"
                ),
                "artifact_id": decision_status["artifact_id"],
                "decision_status": decision_status["decision_status"],
                "reviewer": decision_status["reviewer"],
                "signature_scheme": envelope["signature_scheme"],
                "signer_key_reference": envelope["signer_key_reference"],
                "signature_reference": envelope["signature_reference"],
                "signed_at": envelope["signed_at"],
                "rejection_reasons": list(decision_status["rejection_reasons"]),
                "proves_artifact_requirement": False,
            }
        )
        if enforce_key_registry:
            signed_envelope_items[-1]["key_registry_status"] = "allowed_reviewer_key"
            _attach_reviewer_key_registry_snapshot(
                signed_envelope_items[-1],
                active_registry_snapshot,
                [],
            )
    return signed_envelope_items


def _signed_review_envelope_shape_rejection_reasons(
    envelope: dict[str, Any],
) -> list[str]:
    required_fields = [
        "envelope_id",
        "signature_scheme",
        "signer_key_reference",
        "signature_reference",
        "signed_at",
        "decision",
    ]
    missing_fields = sorted(field for field in required_fields if field not in envelope)
    reasons: list[str] = []
    if missing_fields:
        reasons.append(
            f"missing_signed_envelope_fields: {', '.join(missing_fields)}"
        )
    if "decision" in envelope and not isinstance(envelope["decision"], dict):
        reasons.append("invalid_signed_decision_payload")
    return reasons


def _signed_envelope_key_registry_rejection_reasons(
    envelopes: list[dict[str, Any]],
    reviewer_key_registry: list[dict[str, Any]],
) -> dict[int, list[str]]:
    if not reviewer_key_registry:
        return {}
    registry_by_key = {
        str(entry.get("signer_key_reference") or ""): entry
        for entry in reviewer_key_registry
        if entry.get("signer_key_reference")
    }
    rejection_reasons: dict[int, list[str]] = {}
    for index, envelope in enumerate(envelopes):
        reasons: list[str] = []
        signer_key_reference = str(envelope.get("signer_key_reference") or "")
        registry_entry = registry_by_key.get(signer_key_reference)
        decision = envelope.get("decision")
        reviewer = decision.get("reviewer") if isinstance(decision, dict) else None
        if registry_entry is None:
            reasons.append("signer_key_not_registered")
        elif registry_entry.get("key_status") != "active":
            reasons.append(
                f"signer_key_not_active: {registry_entry.get('key_status')}"
            )
        elif registry_entry.get("reviewer") != reviewer:
            reasons.append(f"signer_key_reviewer_mismatch: expected {reviewer}")
        if reasons:
            rejection_reasons[index] = reasons
    return rejection_reasons


def _attach_reviewer_key_registry_snapshot(
    envelope: dict[str, Any],
    active_registry_snapshot: dict[str, Any] | None,
    key_rejection_reasons: list[str],
) -> None:
    if active_registry_snapshot is None or key_rejection_reasons:
        return
    envelope["key_registry_snapshot_id"] = active_registry_snapshot.get("snapshot_id")
    envelope["key_registry_snapshot_hash"] = active_registry_snapshot.get("snapshot_hash")


def _reviewer_key_registry_snapshot_rejection_reasons(
    snapshots: list[dict[str, Any]],
    *,
    verify_snapshot_chain: bool,
) -> dict[int, list[str]]:
    if not snapshots:
        return {}
    rejection_reasons: dict[int, list[str]] = {}
    expected_previous_hash = "GENESIS"
    for index, snapshot in enumerate(snapshots):
        reasons = _reviewer_key_registry_snapshot_shape_rejection_reasons(snapshot)
        if verify_snapshot_chain:
            for field in ("previous_snapshot_hash", "snapshot_hash"):
                if field not in snapshot:
                    reasons.append(f"missing_registry_snapshot_hash_fields: {field}")
            if snapshot.get("previous_snapshot_hash") != expected_previous_hash:
                reasons.append(
                    "registry_snapshot_hash_chain_mismatch: "
                    f"previous_snapshot_hash must be {expected_previous_hash}"
                )
            if (
                "snapshot_hash" in snapshot
                and snapshot.get("snapshot_hash")
                != _reviewer_key_registry_snapshot_hash(snapshot)
            ):
                reasons.append("registry_snapshot_hash_mismatch")
            expected_previous_hash = str(snapshot.get("snapshot_hash") or "")
        if reasons:
            rejection_reasons[index] = reasons
    return rejection_reasons


def _reviewer_key_registry_snapshot_shape_rejection_reasons(
    snapshot: dict[str, Any],
) -> list[str]:
    required_fields = ["snapshot_id", "recorded_at", "reviewer_keys"]
    missing_fields = sorted(field for field in required_fields if field not in snapshot)
    reasons: list[str] = []
    if missing_fields:
        reasons.append(
            f"missing_registry_snapshot_fields: {', '.join(missing_fields)}"
        )
    if "reviewer_keys" in snapshot and not isinstance(snapshot["reviewer_keys"], list):
        reasons.append("invalid_registry_snapshot_reviewer_keys")
    return reasons


def _reviewer_key_registry_snapshot_hash(snapshot: dict[str, Any]) -> str:
    payload = {
        "previous_snapshot_hash": snapshot.get("previous_snapshot_hash"),
        "recorded_at": snapshot.get("recorded_at"),
        "reviewer_keys": snapshot.get("reviewer_keys"),
        "snapshot_id": snapshot.get("snapshot_id"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


def _latest_verified_reviewer_key_registry_snapshot(
    snapshots: list[dict[str, Any]],
    snapshot_rejection_reasons: dict[int, list[str]],
) -> dict[str, Any] | None:
    verified_snapshots = [
        snapshot
        for index, snapshot in enumerate(snapshots)
        if snapshot_rejection_reasons.get(index, []) == []
    ]
    return verified_snapshots[-1] if verified_snapshots else None


def _summarize_signed_review_envelopes(
    envelopes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "signed_envelopes_total": len(envelopes),
        "signed_envelopes_accepted": sum(
            1
            for envelope in envelopes
            if envelope["signature_status"] == "signature_metadata_accepted"
        ),
        "signed_envelopes_blocked": sum(
            1
            for envelope in envelopes
            if envelope["signature_status"] == "signature_metadata_blocked"
        ),
        "signed_envelopes_with_approved_decisions": sum(
            1
            for envelope in envelopes
            if envelope["decision_status"] == "external_review_approved"
        ),
        "signed_envelopes_with_rejected_decisions": sum(
            1
            for envelope in envelopes
            if envelope["decision_status"] == "external_review_rejected"
        ),
        "artifacts_proven_by_signed_envelope": 0,
    }


def _summarize_reviewer_key_registry(
    reviewer_key_registry: list[dict[str, Any]],
    envelopes: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "registry_entries_total": len(reviewer_key_registry),
        "active_registry_entries": sum(
            1 for entry in reviewer_key_registry if entry.get("key_status") == "active"
        ),
        "revoked_registry_entries": sum(
            1 for entry in reviewer_key_registry if entry.get("key_status") == "revoked"
        ),
        "envelopes_with_allowed_reviewer_key": sum(
            1
            for envelope in envelopes
            if envelope.get("key_registry_status") == "allowed_reviewer_key"
        ),
        "envelopes_blocked_by_reviewer_key": sum(
            1
            for envelope in envelopes
            if envelope.get("key_registry_status") == "blocked_reviewer_key"
        ),
        "artifacts_proven_by_key_registry": 0,
    }


def _summarize_reviewer_key_registry_snapshots(
    snapshots: list[dict[str, Any]],
    snapshot_rejection_reasons: dict[int, list[str]],
    *,
    verify_snapshot_chain: bool,
) -> dict[str, Any]:
    latest_snapshot = _latest_verified_reviewer_key_registry_snapshot(
        snapshots,
        snapshot_rejection_reasons,
    )
    return {
        "registry_snapshots_total": len(snapshots),
        "snapshot_chain_verification_enabled": verify_snapshot_chain,
        "registry_snapshots_verified": sum(
            1
            for index, _snapshot in enumerate(snapshots)
            if snapshot_rejection_reasons.get(index, []) == []
        ),
        "registry_snapshots_blocked": sum(
            1
            for index, _snapshot in enumerate(snapshots)
            if snapshot_rejection_reasons.get(index, []) != []
        ),
        "latest_snapshot_id": latest_snapshot.get("snapshot_id")
        if latest_snapshot
        else "",
        "latest_snapshot_hash": latest_snapshot.get("snapshot_hash")
        if latest_snapshot
        else "",
        "artifacts_proven_by_registry_snapshot": 0,
    }


def _validate_provided_metadata(
    requirement: dict[str, Any],
    artifact: dict[str, Any] | None,
) -> list[str]:
    if artifact is None:
        return []

    rejection_reasons: list[str] = []
    missing_fields = [
        field
        for field in requirement["required_metadata_fields"]
        if field not in artifact or artifact[field] in (None, "")
    ]
    if missing_fields:
        rejection_reasons.append(
            f"missing_metadata_fields: {', '.join(sorted(missing_fields))}"
        )

    for rule in requirement["metadata_validation_rules"]:
        failure = _evaluate_metadata_validation_rule(rule, artifact)
        if failure is not None:
            rejection_reasons.append(failure)

    return rejection_reasons


def _evaluate_metadata_validation_rule(
    rule: dict[str, Any],
    artifact: dict[str, Any],
) -> str | None:
    rule_type = rule["type"]
    if rule_type == "exact_true":
        field = rule["field"]
        if artifact.get(field) is not True:
            return f"metadata_validation_failed: {field} must be true"
        return None

    if rule_type == "minimum_integer":
        field = rule["field"]
        value = artifact.get(field)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = None
        if parsed is None or parsed < int(rule["minimum"]):
            return f"metadata_validation_failed: {field} must be >= {rule['minimum']}"
        return None

    if rule_type == "exact_integer":
        field = rule["field"]
        value = artifact.get(field)
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = None
        if parsed != int(rule["expected"]):
            return f"metadata_validation_failed: {field} must be {rule['expected']}"
        return None

    if rule_type == "positive_decimal":
        field = rule["field"]
        parsed = _parse_decimal(artifact.get(field))
        if parsed is None or parsed <= Decimal("0"):
            return f"metadata_validation_failed: {field} must be > 0"
        return None

    if rule_type == "exact_decimal":
        field = rule["field"]
        parsed = _parse_decimal(artifact.get(field))
        expected = _parse_decimal(rule["expected"])
        if parsed is None or expected is None or parsed != expected:
            return f"metadata_validation_failed: {field} must be {rule['expected']}"
        return None

    if rule_type == "minimum_date_span_days":
        start_field = rule["start_field"]
        end_field = rule["end_field"]
        start = _parse_iso_date(artifact.get(start_field))
        end = _parse_iso_date(artifact.get(end_field))
        minimum_days = int(rule["minimum_days"])
        if start is None or end is None or (end - start).days < minimum_days:
            return (
                "metadata_validation_failed: "
                f"{start_field} to {end_field} must span at least {minimum_days} days"
            )
        return None

    return None


def _build_done_state_gate_metadata_readiness(
    requirements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    requirement_by_id = {requirement["artifact_id"]: requirement for requirement in requirements}
    readiness: list[dict[str, Any]] = []
    for gate, required_artifact_ids in _DONE_STATE_GATES.items():
        accepted_artifact_ids = [
            artifact_id
            for artifact_id in required_artifact_ids
            if requirement_by_id[artifact_id]["status"] == PROOF_METADATA_ACCEPTED_STATUS
        ]
        rejected_artifact_ids = [
            artifact_id
            for artifact_id in required_artifact_ids
            if requirement_by_id[artifact_id]["status"] == PROOF_METADATA_REJECTED_STATUS
        ]
        missing_artifact_ids = [
            artifact_id
            for artifact_id in required_artifact_ids
            if requirement_by_id[artifact_id]["status"] != PROOF_METADATA_ACCEPTED_STATUS
        ]
        if rejected_artifact_ids:
            status = "metadata_rejected"
        elif len(accepted_artifact_ids) == len(required_artifact_ids):
            status = "metadata_submitted_for_review"
        elif accepted_artifact_ids:
            status = "metadata_partially_submitted"
        else:
            status = "metadata_missing"
        readiness.append(
            {
                "gate": gate,
                "status": status,
                "required_artifact_ids": list(required_artifact_ids),
                "accepted_artifact_ids": accepted_artifact_ids,
                "missing_artifact_ids": missing_artifact_ids,
                "rejected_artifact_ids": rejected_artifact_ids,
                "proves_done_state_gate": False,
            }
        )
    return readiness


def _summarize_done_state_gate_metadata_readiness(
    readiness: list[dict[str, Any]]
) -> dict[str, int]:
    return {
        "done_state_gates_total": len(readiness),
        "done_state_gates_with_all_metadata_submitted": sum(
            1 for gate in readiness if gate["status"] == "metadata_submitted_for_review"
        ),
        "done_state_gates_with_partial_metadata": sum(
            1 for gate in readiness if gate["status"] == "metadata_partially_submitted"
        ),
        "done_state_gates_missing_all_metadata": sum(
            1 for gate in readiness if gate["status"] == "metadata_missing"
        ),
        "done_state_gates_with_rejected_metadata": sum(
            1 for gate in readiness if gate["status"] == "metadata_rejected"
        ),
        "done_state_gates_proven_by_metadata": 0,
    }


def _parse_decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _parse_iso_date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
