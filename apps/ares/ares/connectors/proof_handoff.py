"""Shared redacted proof handoff helpers for local sandbox-backed adapters."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from apps.ares.ares.workflows.contract_keys import stable_mapping_token


def build_provider_sandbox_proof_artifact_metadata(
    *,
    provider: str,
    transcript_id: str,
    run_timestamp: str,
    reviewer_reference: str,
    artifact_reference_prefix: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build proof-safe artifact metadata shared by local sandbox adapters."""
    normalized_provider = str(provider).strip()
    normalized_transcript_id = str(transcript_id).strip()
    normalized_prefix = str(artifact_reference_prefix).rstrip("/")
    if not normalized_provider or not normalized_transcript_id or not normalized_prefix:
        raise ValueError("proof metadata is incomplete")
    reference = artifact_path_or_reference or f"{normalized_prefix}/{normalized_transcript_id}"
    return {
        "artifact_id": "provider_sandbox_adapter_evidence",
        "artifact_path_or_reference": reference,
        "provider": normalized_provider,
        "sandbox_or_production_like_tenant": sandbox_or_production_like_tenant,
        "run_timestamp": run_timestamp,
        "operator_or_accountant_reviewer": reviewer_reference,
        "redaction_confirmed": True,
    }


def build_proof_metadata_manifest(
    *,
    artifact: dict[str, Any],
    generated_from: str,
) -> dict[str, Any]:
    """Wrap proof artifact metadata in the benchmark manifest shape."""
    if not isinstance(artifact, dict) or not artifact.get("artifact_id"):
        raise ValueError("artifact metadata is required for manifest generation")
    return {
        "artifacts": [artifact],
        "generated_from": generated_from,
        "redaction_confirmed": True,
    }


def build_external_evidence_bundle(
    *,
    artifact: dict[str, Any],
    transcript_id: str,
    run_timestamp: str,
    reviewer_reference: str,
    bundle_prefix: str,
    envelope_prefix: str,
    snapshot_prefix: str,
    reviewer_role: str = "operator_or_accountant_reviewer",
    signer_key_reference: str = "redacted-reviewer-key-1",
    signature_reference: str = "redacted-signature-reference-1",
    bundle_token_override: str | None = None,
) -> dict[str, Any]:
    """Build a redacted external-evidence bundle shared by local sandbox adapters."""
    if not isinstance(artifact, dict) or not artifact.get("artifact_id"):
        raise ValueError("artifact metadata is required for external evidence handoff")
    normalized_transcript_id = str(transcript_id).strip()
    if not normalized_transcript_id:
        raise ValueError("proof metadata is incomplete")

    bundle_token = str(bundle_token_override).strip() if bundle_token_override is not None else ""
    if not bundle_token:
        bundle_token = stable_mapping_token(
            {
                "transcript_id": normalized_transcript_id,
                "run_timestamp": run_timestamp,
                "reviewer_reference": reviewer_reference,
                "reviewer_role": reviewer_role,
                "signer_key_reference": signer_key_reference,
            }
        )
    reviewer_keys = [
        {
            "reviewer": reviewer_role,
            "signer_key_reference": signer_key_reference,
            "key_status": "active",
        }
    ]
    snapshot = build_reviewer_key_registry_snapshot(
        snapshot_id=f"{snapshot_prefix}-{bundle_token}",
        recorded_at=run_timestamp,
        reviewer_keys=reviewer_keys,
        previous_snapshot_hash="GENESIS",
    )
    decision = {
        "artifact_id": artifact["artifact_id"],
        "decision": "approved",
        "reviewer": reviewer_role,
        "review_reference": reviewer_reference,
        "reviewed_at": run_timestamp,
        "redaction_confirmed": True,
    }
    return {
        "bundle_id": f"{bundle_prefix}-{bundle_token}",
        "generated_at": run_timestamp,
        "redaction_confirmed": True,
        "artifacts": [artifact],
        "review_decisions": [decision],
        "signed_envelopes": [
            {
                "envelope_id": f"{envelope_prefix}-{bundle_token}",
                "signature_scheme": "local_metadata_signature_v1",
                "signer_key_reference": signer_key_reference,
                "signature_reference": signature_reference,
                "signed_at": run_timestamp,
                "decision": decision,
            }
        ],
        "reviewer_key_registry_snapshots": [snapshot],
    }


def build_reviewed_external_evidence_intake(
    *,
    bundle: dict[str, Any],
    transcript_id: str,
    reviewed_at: str,
    reviewer_reference: str,
    provider: str,
    intake_prefix: str,
    operator_login_metadata: dict[str, Any],
    subject_metadata: dict[str, Any] | None = None,
    subject_metadata_kind: str = "generic_subject_identity",
    filing_identity_metadata: dict[str, Any] | None = None,
    review_outcome: str = "metadata_review_complete_not_verified",
    review_rejection_reference: str | None = None,
    review_rejection_reasons: list[str] | None = None,
    review_resubmission_reference: str | None = None,
    prior_review_cycles: list[dict[str, Any]] | None = None,
    artifact_id: str | None = None,
    intake_token_override: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic reviewed-evidence intake payload for local replay."""
    bundle_id = str(bundle.get("bundle_id") or "").strip()
    normalized_transcript_id = str(transcript_id).strip()
    normalized_provider = str(provider).strip()
    normalized_prefix = str(intake_prefix).strip()
    if not bundle_id or not normalized_transcript_id or not normalized_provider or not normalized_prefix:
        raise ValueError("reviewed evidence intake metadata is incomplete")

    resolved_artifact_id = str(artifact_id or "").strip()
    if not resolved_artifact_id:
        artifacts = bundle.get("artifacts") if isinstance(bundle.get("artifacts"), list) else []
        first_artifact = artifacts[0] if artifacts and isinstance(artifacts[0], dict) else {}
        resolved_artifact_id = str(first_artifact.get("artifact_id") or "").strip()
    if not resolved_artifact_id:
        raise ValueError("reviewed evidence intake requires an artifact_id")

    resolved_subject_metadata = subject_metadata
    if resolved_subject_metadata is None and filing_identity_metadata is not None:
        resolved_subject_metadata = filing_identity_metadata
        subject_metadata_kind = "gst_filing_identity"
    if not isinstance(resolved_subject_metadata, dict):
        raise ValueError("reviewed evidence intake requires subject metadata")

    intake_token = str(intake_token_override).strip() if intake_token_override is not None else ""
    if not intake_token:
        intake_token = stable_mapping_token(
            {
                "bundle_id": bundle_id,
                "transcript_id": normalized_transcript_id,
                "reviewed_at": reviewed_at,
                "reviewer_reference": reviewer_reference,
                "provider": normalized_provider,
                "artifact_id": resolved_artifact_id,
                "review_outcome": review_outcome,
                "review_rejection_reference": review_rejection_reference,
                "review_rejection_reasons": review_rejection_reasons or [],
                "review_resubmission_reference": review_resubmission_reference,
                "prior_review_cycles": prior_review_cycles or [],
                "operator_login_metadata": operator_login_metadata,
                "subject_metadata_kind": subject_metadata_kind,
                "subject_metadata": resolved_subject_metadata,
            }
        )

    intake = {
        "intake_id": f"{normalized_prefix}-{intake_token}",
        "bundle_id": bundle_id,
        "transcript_id": normalized_transcript_id,
        "artifact_id": resolved_artifact_id,
        "provider": normalized_provider,
        "reviewed_at": reviewed_at,
        "reviewer_reference": reviewer_reference,
        "review_scope": "reviewed_external_evidence_intake_only",
        "review_outcome": review_outcome,
        "redaction_confirmed": True,
        "operator_login_metadata": operator_login_metadata,
        "subject_metadata_kind": subject_metadata_kind,
        "subject_metadata": resolved_subject_metadata,
    }
    if review_rejection_reference is not None:
        intake["review_rejection_reference"] = review_rejection_reference
    if review_rejection_reasons is not None:
        intake["review_rejection_reasons"] = list(review_rejection_reasons)
    if review_resubmission_reference is not None:
        intake["review_resubmission_reference"] = review_resubmission_reference
    if prior_review_cycles is not None:
        intake["prior_review_cycles"] = [dict(cycle) for cycle in prior_review_cycles]
    if subject_metadata_kind == "gst_filing_identity":
        intake["filing_identity_metadata"] = resolved_subject_metadata
    return intake


def build_reviewer_key_registry_snapshot(
    *,
    snapshot_id: str,
    recorded_at: str,
    reviewer_keys: list[dict[str, Any]],
    previous_snapshot_hash: str,
) -> dict[str, Any]:
    """Build a deterministic reviewer-key registry snapshot for handoff verification."""
    snapshot = {
        "snapshot_id": snapshot_id,
        "recorded_at": recorded_at,
        "reviewer_keys": reviewer_keys,
        "previous_snapshot_hash": previous_snapshot_hash,
    }
    payload = {
        "previous_snapshot_hash": previous_snapshot_hash,
        "recorded_at": recorded_at,
        "reviewer_keys": reviewer_keys,
        "snapshot_id": snapshot_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    snapshot["snapshot_hash"] = hashlib.sha256(encoded).hexdigest()
    return snapshot
