"""Local WhatsApp sandbox adapter scaffold for signed webhook and template payload tests."""

from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime
from typing import Any, Mapping

from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.connectors.message_ingest import (
    WHATSAPP_SANDBOX_INGEST_LIMITATION,
    ingest_whatsapp_sandbox_payload,
)
from apps.ares.ares.connectors.proof_handoff import (
    build_external_evidence_bundle,
    build_proof_metadata_manifest,
    build_provider_sandbox_proof_artifact_metadata,
    build_reviewed_external_evidence_intake,
)
from apps.ares.ares.workflows.contract_keys import stable_mapping_token
from apps.ares.ares.workflows.integration_preflight import PROVIDER_REQUIREMENTS
from apps.ares.ares.workflows.whatsapp_business import (
    WHATSAPP_BUSINESS_LIMITATION,
    record_whatsapp_delivery_receipt,
)

WHATSAPP_SANDBOX_ADAPTER_LIMITATION = (
    "Local WhatsApp sandbox adapter scaffold only; no Meta webhook registration, template send, "
    "message fetch, or production WhatsApp API call was performed."
)
WHATSAPP_SANDBOX_HEALTHCHECK_LIMITATION = (
    "Local WhatsApp sandbox healthcheck only; no secret values were inspected and no Meta sandbox "
    "tenant, webhook, or network endpoint was contacted."
)
WHATSAPP_SANDBOX_PROOF_LIMITATION = (
    "Local WhatsApp sandbox proof transcript only; no Meta webhook console, delivery analytics, "
    "template registration panel, or external tenant evidence was inspected."
)
WHATSAPP_SIGNATURE_HEADER = "x-hub-signature-256"
WHATSAPP_SIGNATURE_SCHEME = "hmac_sha256"
WHATSAPP_REQUIRED_SANDBOX_ENV_NAMES = tuple(PROVIDER_REQUIREMENTS["whatsapp_business"]) + (
    "META_WABA_SANDBOX_APP_SECRET",
    "META_WABA_SANDBOX_BUSINESS_ACCOUNT_ID",
)

LANGUAGE_CODE_MAP = {
    "english_hinglish": "en",
    "english": "en",
    "hindi": "hi",
    "marathi": "mr",
    "gujarati": "gu",
    "punjabi": "pa",
    "bengali": "bn",
    "tamil": "ta",
    "telugu": "te",
    "kannada": "kn",
    "malayalam": "ml",
}


def prepare_whatsapp_sandbox_template_payload(
    *,
    approval_data: dict[str, Any],
    phone_number_id: str,
    business_account_id: str,
) -> dict[str, Any]:
    """Build a local Meta-style template payload from the approval-gated contract."""
    import os
    import httpx

    recipient_phone = str(approval_data.get("recipient_phone") or "").strip()
    template_name = str(approval_data.get("template_name") or "").strip()
    body = str(approval_data.get("body") or "").strip()
    if not recipient_phone or not template_name or not body:
        raise ValueError("recipient_phone, template_name, and body are required for WhatsApp sandbox payload shaping")

    selected_language = str(approval_data.get("selected_language") or "english_hinglish").strip().lower()
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": recipient_phone,
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": _language_code(selected_language)},
            "components": [
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": body}],
                }
            ],
        },
    }

    access_token = os.getenv("META_WABA_SANDBOX_ACCESS_TOKEN")
    api_called = False
    send_performed = False
    live_response = None
    status = "payload_prepared"

    if access_token:
        try:
            url = f"https://graph.facebook.com/v18.0/{phone_number_id.strip()}/messages"
            headers = {
                "Authorization": f"Bearer {access_token.strip()}",
                "Content-Type": "application/json",
            }
            resp = httpx.post(url, headers=headers, json=payload, timeout=5.0)
            api_called = True
            if resp.status_code == 200:
                send_performed = True
                status = "payload_prepared_and_sent"
                live_response = resp.json()
            else:
                status = f"payload_prepared_but_failed_status_{resp.status_code}"
                live_response = resp.text
        except Exception as e:
            status = "payload_prepared_but_network_error"
            live_response = str(e)

    return {
        "mode": "live_sandbox_active" if send_performed else "local_contract_mock",
        "status": status,
        "request": {
            "provider": "whatsapp_business",
            "business_account_id": business_account_id.strip(),
            "phone_number_id": phone_number_id.strip(),
            "approval_id": approval_data.get("approval_id"),
            "idempotency_key": approval_data.get("idempotency_key"),
            "selected_language": selected_language,
            "payload": payload,
        },
        "live_response": live_response,
        "audit": {
            "external_whatsapp_business_api_called": api_called,
            "template_send_performed": send_performed,
            "webhook_signature_verified": False,
            "limitation": None if send_performed else WHATSAPP_SANDBOX_ADAPTER_LIMITATION,
            "workflow_limitation": WHATSAPP_BUSINESS_LIMITATION,
        },
    }


def ingest_whatsapp_sandbox_webhook(
    *,
    repository: BusinessRepository,
    client_id: str,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None = None,
    webhook_app_secret: str | None = None,
    approval_by_provider_message_id: Mapping[str, str | None] | None = None,
    received_at: datetime | None = None,
) -> dict[str, Any]:
    """Verify and normalize a local WhatsApp sandbox webhook payload."""
    signature_status = _verify_whatsapp_signature(
        payload=payload,
        headers=headers,
        webhook_app_secret=webhook_app_secret,
    )
    signature_verified = signature_status == "verified_contract_fixture"
    if not signature_verified:
        return {
            "mode": "local_contract_mock",
            "status": "blocked_unverified_signature",
            "messages": [],
            "delivery_updates": [],
            "delivery_receipts": [],
            "audit": {
                "provider": "whatsapp_business",
                "sandbox_payload_processed": False,
                "webhook_signature_verified": False,
                "live_api_called": False,
                "production_message_processed": False,
                "limitation": WHATSAPP_SANDBOX_INGEST_LIMITATION,
            },
            "adapter": {
                "connector": "whatsapp_sandbox",
                "signature_scheme": WHATSAPP_SIGNATURE_SCHEME,
                "signature_verified": False,
                "meta_webhook_registered": False,
                "delivery_sink_invoked": False,
                "template_send_performed": False,
                "live_api_called": False,
                "limitation": WHATSAPP_SANDBOX_ADAPTER_LIMITATION,
            },
        }

    normalized = ingest_whatsapp_sandbox_payload(
        client_id=client_id,
        payload=payload,
        received_at=received_at,
    )
    delivery_receipts: list[dict[str, Any]] = []
    approval_lookup = approval_by_provider_message_id or {}
    for update in normalized["delivery_updates"]:
        delivery_receipts.append(
            record_whatsapp_delivery_receipt(
                repository=repository,
                client_id=client_id,
                approval_id=approval_lookup.get(update["provider_message_id"]),
                provider_message_id=update["provider_message_id"],
                recipient_phone=update["recipient_phone"],
                status=update["status"],
            )
        )

    normalized["audit"]["webhook_signature_verified"] = True
    normalized["delivery_receipts"] = delivery_receipts
    normalized["proof_transcript"] = _build_whatsapp_sandbox_proof_transcript(
        payload=payload,
        messages=normalized["messages"],
        delivery_updates=normalized["delivery_updates"],
        signature_verified=True,
    )
    normalized["adapter"] = {
        "connector": "whatsapp_sandbox",
        "signature_scheme": WHATSAPP_SIGNATURE_SCHEME,
        "signature_verified": True,
        "meta_webhook_registered": False,
        "delivery_sink_invoked": bool(delivery_receipts),
        "template_send_performed": False,
        "live_api_called": False,
        "limitation": WHATSAPP_SANDBOX_ADAPTER_LIMITATION,
        "workflow_limitation": WHATSAPP_SANDBOX_INGEST_LIMITATION,
    }
    return normalized


def build_whatsapp_sandbox_proof_artifact_metadata(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build proof-safe metadata for a verified WhatsApp sandbox adapter run."""
    adapter = adapter_result.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("connector") != "whatsapp_sandbox":
        raise ValueError("adapter_result must come from whatsapp_sandbox")
    proof_transcript = adapter_result.get("proof_transcript")
    if not isinstance(proof_transcript, dict):
        raise ValueError("adapter_result must include proof_transcript metadata")
    if not proof_transcript.get("signature_verified"):
        raise ValueError("proof_transcript must come from a signature-verified WhatsApp sandbox run")
    transcript_id = str(proof_transcript.get("transcript_id") or "").strip()
    return build_provider_sandbox_proof_artifact_metadata(
        provider="whatsapp_business",
        transcript_id=transcript_id,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        artifact_reference_prefix="redacted://whatsapp_business",
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )


def build_whatsapp_sandbox_proof_metadata_manifest(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build an ingestible redacted manifest for WhatsApp sandbox proof review handoff."""
    artifact = build_whatsapp_sandbox_proof_artifact_metadata(
        adapter_result=adapter_result,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )
    return build_proof_metadata_manifest(artifact=artifact, generated_from="whatsapp_sandbox")


def build_whatsapp_sandbox_external_evidence_bundle(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    reviewer_role: str = "operator_or_accountant_reviewer",
    signer_key_reference: str = "redacted-reviewer-key-1",
    signature_reference: str = "redacted-signature-reference-1",
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
    bundle_token_override: str | None = None,
) -> dict[str, Any]:
    """Build a redacted external-evidence bundle for WhatsApp sandbox proof handoff."""
    artifact = build_whatsapp_sandbox_proof_artifact_metadata(
        adapter_result=adapter_result,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )
    proof_transcript = adapter_result.get("proof_transcript")
    if not isinstance(proof_transcript, dict):
        raise ValueError("adapter_result must include proof_transcript metadata")
    transcript_id = str(proof_transcript.get("transcript_id") or "").strip()
    return build_external_evidence_bundle(
        artifact=artifact,
        transcript_id=transcript_id,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        reviewer_role=reviewer_role,
        signer_key_reference=signer_key_reference,
        signature_reference=signature_reference,
        bundle_prefix="external-evidence-bundle-whatsapp",
        envelope_prefix="signed-whatsapp-proof",
        snapshot_prefix="registry-snapshot-whatsapp",
        bundle_token_override=bundle_token_override,
    )


def build_whatsapp_sandbox_reviewed_evidence_intake(
    *,
    adapter_result: dict[str, Any],
    external_evidence_bundle: dict[str, Any],
    reviewed_at: str,
    reviewer_reference: str,
    operator_login_reference: str = "redacted-whatsapp-operator-login-1",
    operator_session_reference: str = "redacted-whatsapp-session-1",
    review_outcome: str = "metadata_review_complete_not_verified",
    intake_token_override: str | None = None,
) -> dict[str, Any]:
    """Build a redacted reviewed-evidence intake payload for WhatsApp sandbox replay."""
    adapter = adapter_result.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("connector") != "whatsapp_sandbox":
        raise ValueError("adapter_result must come from whatsapp_sandbox")
    proof_transcript = adapter_result.get("proof_transcript")
    if not isinstance(proof_transcript, dict):
        raise ValueError("adapter_result must include proof_transcript metadata")
    delivery_updates = adapter_result.get("delivery_updates")
    updates = delivery_updates if isinstance(delivery_updates, list) else []
    first_update = updates[0] if updates and isinstance(updates[0], dict) else {}
    messages = adapter_result.get("messages")
    first_message = messages[0] if isinstance(messages, list) and messages else None
    message_reference = str(getattr(first_message, "file_id", "") or "").strip()
    provider_message_reference = str(first_update.get("provider_message_id") or "").strip()
    return build_reviewed_external_evidence_intake(
        bundle=external_evidence_bundle,
        transcript_id=str(proof_transcript.get("transcript_id") or "").strip(),
        reviewed_at=reviewed_at,
        reviewer_reference=reviewer_reference,
        provider="whatsapp_business",
        intake_prefix="reviewed-whatsapp-evidence-intake",
        review_outcome=review_outcome,
        intake_token_override=intake_token_override,
        operator_login_metadata={
            "actor_role": "operator_or_accountant",
            "login_reference": operator_login_reference,
            "session_reference": operator_session_reference,
            "login_surface": "whatsapp_business_sandbox_dashboard",
            "redaction_confirmed": True,
        },
        subject_metadata_kind="whatsapp_message_identity",
        subject_metadata={
            "subject_reference": message_reference or provider_message_reference or "redacted://whatsapp_business/empty",
            "subject_scope": "whatsapp_template_delivery_review",
            "operation": "whatsapp_sandbox_delivery_review",
            "portal_reference": str(proof_transcript.get("payload_reference") or "").strip(),
            "redaction_confirmed": True,
        },
    )


def build_whatsapp_sandbox_healthcheck(
    *,
    configured_env_names: set[str] | None = None,
    safe_test_environment_confirmed: bool = False,
) -> dict[str, Any]:
    configured = configured_env_names or set()
    missing_env_names = [name for name in WHATSAPP_REQUIRED_SANDBOX_ENV_NAMES if name not in configured]
    blocked_reasons: list[str] = []
    if missing_env_names:
        blocked_reasons.append(f"missing sandbox environment names: {', '.join(missing_env_names)}")
    if not safe_test_environment_confirmed:
        blocked_reasons.append("safe non-production sandbox tenant not confirmed for whatsapp_business")

    return {
        "mode": "local_contract_mock",
        "provider": "whatsapp_business",
        "status": "ready_for_local_adapter_tests" if not blocked_reasons else "blocked",
        "required_env_names": list(WHATSAPP_REQUIRED_SANDBOX_ENV_NAMES),
        "missing_env_names": missing_env_names,
        "safe_test_environment_confirmed": safe_test_environment_confirmed,
        "fixture_families": [
            "inbound message webhook payload",
            "delivery status webhook payload",
            "template payload shaping contract",
        ],
        "webhook_signature_scheme": WHATSAPP_SIGNATURE_SCHEME,
        "can_run_local_adapter_tests": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": WHATSAPP_SANDBOX_HEALTHCHECK_LIMITATION,
        },
    }


def _verify_whatsapp_signature(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_app_secret: str | None,
) -> str:
    if not webhook_app_secret:
        return "not_verified_contract_mock"
    signature = _header_value(headers or {}, WHATSAPP_SIGNATURE_HEADER)
    if not signature:
        return "not_verified_contract_mock"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    expected_digest = hmac.new(
        webhook_app_secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    expected_signature = f"sha256={expected_digest}"
    if hmac.compare_digest(signature, expected_signature):
        return "verified_contract_fixture"
    return "not_verified_contract_mock"


def _header_value(headers: Mapping[str, Any], expected_name: str) -> str:
    for key, value in headers.items():
        if str(key).strip().lower() == expected_name:
            return str(value).strip()
    return ""


def _language_code(selected_language: str) -> str:
    return LANGUAGE_CODE_MAP.get(selected_language, "en")


def _build_whatsapp_sandbox_proof_transcript(
    *,
    payload: dict[str, Any],
    messages: list[Any],
    delivery_updates: list[dict[str, Any]],
    signature_verified: bool,
) -> dict[str, Any]:
    message_ids = [str(getattr(message, "file_id", "") or "").strip() for message in messages if str(getattr(message, "file_id", "") or "").strip()]
    provider_message_ids = [str(update.get("provider_message_id") or "").strip() for update in delivery_updates if str(update.get("provider_message_id") or "").strip()]
    transcript_payload = {
        "entry_count": len(payload.get("entry") or []) if isinstance(payload.get("entry"), list) else 0,
        "message_ids": message_ids,
        "provider_message_ids": provider_message_ids,
        "signature_verified": signature_verified,
    }
    return {
        "transcript_id": f"whatsapp_txn_{stable_mapping_token(transcript_payload)}",
        "payload_reference": (
            f"redacted://whatsapp_business/{message_ids[0]}"
            if message_ids
            else f"redacted://whatsapp_business/{provider_message_ids[0]}"
            if provider_message_ids
            else "redacted://whatsapp_business/empty"
        ),
        "proof_safe": True,
        "raw_payload_persisted": False,
        "customer_data_redacted": True,
        "signature_verified": signature_verified,
        "captured_fields": [
            "entry_count",
            "message_ids",
            "provider_message_ids",
            "signature_verified",
        ],
        "limitation": WHATSAPP_SANDBOX_PROOF_LIMITATION,
    }
