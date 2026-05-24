"""Local payment gateway sandbox adapter scaffold for provider-shaped webhooks."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import date, datetime, timezone
from typing import Any, Mapping

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.proof_handoff import (
    build_external_evidence_bundle,
    build_proof_metadata_manifest,
    build_provider_sandbox_proof_artifact_metadata,
    build_reviewed_external_evidence_intake,
)
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_mapping_token
from apps.ares.ares.workflows.integration_preflight import PROVIDER_REQUIREMENTS
from apps.ares.ares.workflows.payment_gateway import (
    LOCAL_PAYMENT_GATEWAY_LIMITATION,
    ingest_payment_gateway_webhook_contract,
)

PAYMENT_GATEWAY_SANDBOX_ADAPTER_LIMITATION = (
    "Local payment gateway sandbox adapter scaffold only; no live gateway API call, webhook registration, "
    "refund execution, settlement pull, or bank execution was performed."
)
PAYMENT_GATEWAY_SANDBOX_HEALTHCHECK_LIMITATION = (
    "Local payment gateway sandbox healthcheck only; no secret values were inspected and no provider "
    "network or sandbox webhook endpoint was contacted."
)
PAYMENT_GATEWAY_SANDBOX_PROOF_LIMITATION = (
    "Local payment gateway sandbox proof transcript only; no live provider console, webhook endpoint, "
    "or settlement evidence was inspected."
)
RAZORPAY_SIGNATURE_HEADER = "x-razorpay-signature"
RAZORPAY_SIGNATURE_SCHEME = "hmac_sha256"
RAZORPAY_SANDBOX_FIXTURE_FAMILIES = (
    "payment.captured webhook payload",
    "payment.failed webhook payload",
    "payment.refunded webhook payload",
)
CASHFREE_SIGNATURE_HEADER = "x-cashfree-signature"
CASHFREE_SIGNATURE_SCHEME = "hmac_sha256"
CASHFREE_SANDBOX_FIXTURE_FAMILIES = (
    "payment.success webhook payload",
    "payment.failed webhook payload",
)
PHONEPE_SIGNATURE_HEADER = "x-verify"
PHONEPE_SIGNATURE_SCHEME = "sha256_base64_path_salt_index"
PHONEPE_WEBHOOK_PATH = "/v1/notifications/payment"
PHONEPE_SANDBOX_FIXTURE_FAMILIES = (
    "checkout.order.completed webhook payload",
    "checkout.order.failed webhook payload",
)
PAYMENT_GATEWAY_SANDBOX_PROVIDER_CONFIG = {
    "razorpay": {
        "signature_scheme": RAZORPAY_SIGNATURE_SCHEME,
        "fixture_families": list(RAZORPAY_SANDBOX_FIXTURE_FAMILIES),
    },
    "cashfree": {
        "signature_scheme": CASHFREE_SIGNATURE_SCHEME,
        "fixture_families": list(CASHFREE_SANDBOX_FIXTURE_FAMILIES),
    },
    "phonepe": {
        "signature_scheme": PHONEPE_SIGNATURE_SCHEME,
        "fixture_families": list(PHONEPE_SANDBOX_FIXTURE_FAMILIES),
    },
}
SUPPORTED_PAYMENT_GATEWAY_SANDBOX_PROVIDERS = frozenset(PAYMENT_GATEWAY_SANDBOX_PROVIDER_CONFIG)


def ingest_payment_gateway_sandbox_payload(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    provider: str,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None = None,
    webhook_signing_secret: str | None = None,
) -> dict[str, Any]:
    """Normalize a sandbox webhook payload and route it into the local payment contract."""
    normalized_provider = _normalize_provider(provider)
    if normalized_provider == "razorpay":
        normalized = _normalize_razorpay_sandbox_webhook(
            payload=payload,
            headers=headers,
            webhook_signing_secret=webhook_signing_secret,
        )
    elif normalized_provider == "cashfree":
        normalized = _normalize_cashfree_sandbox_webhook(
            payload=payload,
            headers=headers,
            webhook_signing_secret=webhook_signing_secret,
        )
    elif normalized_provider == "phonepe":
        normalized = _normalize_phonepe_sandbox_webhook(
            payload=payload,
            headers=headers,
            webhook_signing_secret=webhook_signing_secret,
        )
    else:  # pragma: no cover - kept for future provider expansion
        raise ValueError(f"Unsupported payment gateway sandbox provider: {provider}")

    workflow_result = ingest_payment_gateway_webhook_contract(
        repository=repository,
        approvals=approvals,
        client_id=client_id,
        provider=normalized_provider,
        webhook_event=normalized["webhook_event"],
    )

    signature_verified = normalized["webhook_event"]["signature_verification_status"] in {
        "verified",
        "verified_contract_fixture",
    }
    provider_config = PAYMENT_GATEWAY_SANDBOX_PROVIDER_CONFIG[normalized_provider]
    proof_transcript = _build_payment_gateway_proof_transcript(
        provider=normalized_provider,
        normalized_event_type=normalized["webhook_event"]["event_type"],
        payment_id=normalized["webhook_event"]["payment_id"],
        payload_reference=normalized["provider_payload"]["payload_reference"],
        signature_verified=signature_verified,
    )
    return {
        **workflow_result,
        "provider_payload": normalized["provider_payload"],
        "proof_transcript": proof_transcript,
        "adapter": {
            "connector": "payment_gateway_sandbox",
            "provider": normalized_provider,
            "signature_scheme": provider_config["signature_scheme"],
            "signature_verified": signature_verified,
            "normalized_event_type": normalized["webhook_event"]["event_type"],
            "live_webhook_received": False,
            "provider_api_called": False,
            "webhook_registration_performed": False,
            "refund_execution_performed": False,
            "settlement_fetch_performed": False,
            "limitation": PAYMENT_GATEWAY_SANDBOX_ADAPTER_LIMITATION,
            "workflow_limitation": LOCAL_PAYMENT_GATEWAY_LIMITATION,
        },
    }


def build_payment_gateway_sandbox_proof_artifact_metadata(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build proof-safe metadata for a verified payment sandbox adapter run."""
    adapter = adapter_result.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("connector") != "payment_gateway_sandbox":
        raise ValueError("adapter_result must come from payment_gateway_sandbox")
    proof_transcript = adapter_result.get("proof_transcript")
    if not isinstance(proof_transcript, dict):
        raise ValueError("adapter_result must include proof_transcript metadata")
    if not proof_transcript.get("signature_verified"):
        raise ValueError("proof_transcript must come from a signature-verified sandbox adapter run")
    transcript_id = str(proof_transcript.get("transcript_id") or "").strip()
    provider = str(adapter.get("provider") or "").strip()
    return build_provider_sandbox_proof_artifact_metadata(
        provider=provider,
        transcript_id=transcript_id,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        artifact_reference_prefix=f"redacted://payment_gateway/{provider}",
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )


def build_payment_gateway_sandbox_proof_metadata_manifest(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build an ingestible redacted manifest for benchmark proof review handoff."""
    artifact = build_payment_gateway_sandbox_proof_artifact_metadata(
        adapter_result=adapter_result,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )
    return build_proof_metadata_manifest(artifact=artifact, generated_from="payment_gateway_sandbox")


def build_payment_gateway_sandbox_external_evidence_bundle(
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
    """Build a redacted external-evidence bundle for payment sandbox proof handoff."""
    artifact = build_payment_gateway_sandbox_proof_artifact_metadata(
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
        bundle_prefix="external-evidence-bundle-payment",
        envelope_prefix="signed-payment-proof",
        snapshot_prefix="registry-snapshot-payment",
        bundle_token_override=bundle_token_override,
    )


def build_payment_gateway_sandbox_reviewed_evidence_intake(
    *,
    adapter_result: dict[str, Any],
    external_evidence_bundle: dict[str, Any],
    reviewed_at: str,
    reviewer_reference: str,
    operator_login_reference: str = "redacted-payment-operator-login-1",
    operator_session_reference: str = "redacted-payment-session-1",
    review_outcome: str = "metadata_review_complete_not_verified",
    intake_token_override: str | None = None,
) -> dict[str, Any]:
    """Build a redacted reviewed-evidence intake payload for payment sandbox replay."""
    adapter = adapter_result.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("connector") != "payment_gateway_sandbox":
        raise ValueError("adapter_result must come from payment_gateway_sandbox")
    proof_transcript = adapter_result.get("proof_transcript")
    if not isinstance(proof_transcript, dict):
        raise ValueError("adapter_result must include proof_transcript metadata")
    provider_payload = adapter_result.get("provider_payload")
    provider_payload_mapping = provider_payload if isinstance(provider_payload, Mapping) else {}
    provider = str(adapter.get("provider") or "").strip()
    return build_reviewed_external_evidence_intake(
        bundle=external_evidence_bundle,
        transcript_id=str(proof_transcript.get("transcript_id") or "").strip(),
        reviewed_at=reviewed_at,
        reviewer_reference=reviewer_reference,
        provider=provider,
        intake_prefix="reviewed-payment-evidence-intake",
        review_outcome=review_outcome,
        intake_token_override=intake_token_override,
        operator_login_metadata={
            "actor_role": "operator_or_accountant",
            "login_reference": operator_login_reference,
            "session_reference": operator_session_reference,
            "login_surface": f"{provider}_sandbox_dashboard",
            "redaction_confirmed": True,
        },
        subject_metadata_kind="payment_settlement_identity",
        subject_metadata={
            "subject_reference": str(provider_payload_mapping.get("payment_id") or "").strip(),
            "subject_scope": str(
                adapter.get("normalized_event_type") or provider_payload_mapping.get("event_type") or "payment_settlement_review"
            ).strip(),
            "operation": "payment_gateway_webhook_review",
            "portal_reference": str(
                provider_payload_mapping.get("payload_reference")
                or proof_transcript.get("payload_reference")
                or provider_payload_mapping.get("payment_id")
                or ""
            ).strip(),
            "redaction_confirmed": True,
        },
    )


def build_payment_gateway_sandbox_healthcheck(
    *,
    provider: str,
    configured_env_names: set[str] | None = None,
    safe_test_environment_confirmed: bool = False,
) -> dict[str, Any]:
    """Build an adapter-facing local healthcheck gate without contacting any provider."""
    normalized_provider = _normalize_provider(provider)
    configured = configured_env_names or set()
    required_env_names = list(PROVIDER_REQUIREMENTS[normalized_provider])
    provider_config = PAYMENT_GATEWAY_SANDBOX_PROVIDER_CONFIG[normalized_provider]
    missing_env_names = [name for name in required_env_names if name not in configured]

    blocked_reasons: list[str] = []
    if missing_env_names:
        blocked_reasons.append(f"missing sandbox environment names: {', '.join(missing_env_names)}")
    if not safe_test_environment_confirmed:
        blocked_reasons.append(f"safe non-production sandbox tenant not confirmed for {normalized_provider}")

    status = "ready_for_local_adapter_tests" if not blocked_reasons else "blocked"
    return {
        "mode": "local_contract_mock",
        "provider": normalized_provider,
        "status": status,
        "required_env_names": required_env_names,
        "missing_env_names": missing_env_names,
        "safe_test_environment_confirmed": safe_test_environment_confirmed,
        "fixture_families": list(provider_config["fixture_families"]),
        "webhook_signature_scheme": provider_config["signature_scheme"],
        "can_run_local_adapter_tests": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": PAYMENT_GATEWAY_SANDBOX_HEALTHCHECK_LIMITATION,
        },
    }


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_PAYMENT_GATEWAY_SANDBOX_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PAYMENT_GATEWAY_SANDBOX_PROVIDERS))
        raise ValueError(f"Unsupported payment gateway sandbox provider: {provider}. Supported: {supported}")
    return normalized


def _build_payment_gateway_proof_transcript(
    *,
    provider: str,
    normalized_event_type: str,
    payment_id: str,
    payload_reference: str | None,
    signature_verified: bool,
) -> dict[str, Any]:
    transcript_payload = {
        "provider": provider,
        "normalized_event_type": normalized_event_type,
        "payment_id": payment_id,
        "payload_reference": payload_reference,
        "signature_verified": signature_verified,
    }
    return {
        "transcript_id": f"payment_txn_{stable_mapping_token(transcript_payload)}",
        "payload_reference": payload_reference,
        "proof_safe": True,
        "raw_payload_persisted": False,
        "customer_data_redacted": True,
        "signature_verified": signature_verified,
        "captured_fields": [
            "provider",
            "normalized_event_type",
            "payment_id",
            "payload_reference",
            "signature_verified",
        ],
        "limitation": PAYMENT_GATEWAY_SANDBOX_PROOF_LIMITATION,
    }
def _normalize_razorpay_sandbox_webhook(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_signing_secret: str | None,
) -> dict[str, Any]:
    event_type = str(payload.get("event") or "").strip().lower()
    payment_entity = _payment_entity(payload)
    notes = payment_entity.get("notes") if isinstance(payment_entity.get("notes"), dict) else {}
    acquirer_data = payment_entity.get("acquirer_data") if isinstance(payment_entity.get("acquirer_data"), dict) else {}
    amount_paise = int(payment_entity.get("amount") or 0)
    paid_on = _date_from_timestamp(
        payment_entity.get("captured_at") or payment_entity.get("created_at") or payload.get("created_at")
    )
    signature_status = _verify_razorpay_signature(
        payload=payload,
        headers=headers,
        webhook_signing_secret=webhook_signing_secret,
    )

    webhook_event = {
        "provider": "razorpay",
        "sandbox": True,
        "event_type": event_type,
        "payment_id": str(payment_entity.get("id") or "").strip(),
        "invoice_id": str(notes.get("invoice_id") or "").strip() or None,
        "customer_id": str(notes.get("customer_id") or notes.get("party_id") or "").strip() or None,
        "amount": round(amount_paise / 100.0, 2),
        "utr": str(acquirer_data.get("rrn") or notes.get("utr") or payment_entity.get("reference") or "").strip() or None,
        "paid_on": paid_on.isoformat() if paid_on else None,
        "signature_verification_status": signature_status,
        "payload_reference": str(payload.get("payload_reference") or "").strip() or None,
    }
    provider_payload = {
        "provider": "razorpay",
        "account_id": str(payload.get("account_id") or "").strip() or None,
        "event_type": event_type,
        "payment_status": str(payment_entity.get("status") or "").strip().lower() or None,
        "payment_id": webhook_event["payment_id"],
        "payload_reference": webhook_event["payload_reference"],
        "contains_redacted_test_data": bool(payload.get("contains_redacted_test_data")),
    }
    return {"webhook_event": webhook_event, "provider_payload": provider_payload}


def _normalize_cashfree_sandbox_webhook(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_signing_secret: str | None,
) -> dict[str, Any]:
    event_type = _normalize_cashfree_event_type(payload)
    payment_entity = _cashfree_payment_entity(payload)
    order_entity = _cashfree_order_entity(payload)
    customer_entity = _cashfree_customer_entity(payload)
    metadata = _cashfree_metadata(payload)
    amount = float(payment_entity.get("payment_amount") or order_entity.get("order_amount") or 0)
    paid_on = _date_from_timestamp(payment_entity.get("payment_time") or payload.get("event_time"))
    signature_status = _verify_cashfree_signature(
        payload=payload,
        headers=headers,
        webhook_signing_secret=webhook_signing_secret,
    )

    webhook_event = {
        "provider": "cashfree",
        "sandbox": True,
        "event_type": event_type,
        "payment_id": str(payment_entity.get("cf_payment_id") or "").strip(),
        "invoice_id": str(order_entity.get("order_id") or "").strip() or None,
        "customer_id": str(customer_entity.get("customer_id") or "").strip() or None,
        "amount": round(amount, 2),
        "utr": str(metadata.get("utr") or payment_entity.get("payment_message") or "").strip() or None,
        "paid_on": paid_on.isoformat() if paid_on else None,
        "signature_verification_status": signature_status,
        "payload_reference": str(payload.get("payload_reference") or "").strip() or None,
    }
    provider_payload = {
        "provider": "cashfree",
        "event_type": str(payload.get("type") or "").strip() or None,
        "payment_status": str(payment_entity.get("payment_status") or "").strip().lower() or None,
        "payment_id": webhook_event["payment_id"],
        "payload_reference": webhook_event["payload_reference"],
        "contains_redacted_test_data": bool(payload.get("contains_redacted_test_data")),
    }
    return {"webhook_event": webhook_event, "provider_payload": provider_payload}


def _normalize_phonepe_sandbox_webhook(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_signing_secret: str | None,
) -> dict[str, Any]:
    payment_entity = _phonepe_payment_entity(payload)
    meta_info = _phonepe_meta_info(payment_entity)
    event_type = _normalize_phonepe_event_type(payload)
    amount_paise = int(payment_entity.get("amount") or 0)
    paid_on = _date_from_timestamp(payload.get("eventTime"))
    signature_status = _verify_phonepe_signature(
        payload=payload,
        headers=headers,
        webhook_signing_secret=webhook_signing_secret,
    )

    webhook_event = {
        "provider": "phonepe",
        "sandbox": True,
        "event_type": event_type,
        "payment_id": str(payment_entity.get("transactionId") or "").strip(),
        "invoice_id": str(payment_entity.get("merchantTransactionId") or "").strip() or None,
        "customer_id": str(meta_info.get("customerId") or "").strip() or None,
        "amount": round(amount_paise / 100.0, 2),
        "utr": str(meta_info.get("utr") or payment_entity.get("transactionId") or "").strip() or None,
        "paid_on": paid_on.isoformat() if paid_on else None,
        "signature_verification_status": signature_status,
        "payload_reference": str(payload.get("payload_reference") or "").strip() or None,
    }
    provider_payload = {
        "provider": "phonepe",
        "event_type": str(payload.get("event") or "").strip() or None,
        "payment_status": str(payment_entity.get("state") or "").strip().lower() or None,
        "payment_id": webhook_event["payment_id"],
        "payload_reference": webhook_event["payload_reference"],
        "contains_redacted_test_data": bool(payload.get("contains_redacted_test_data")),
    }
    return {"webhook_event": webhook_event, "provider_payload": provider_payload}


def _payment_entity(payload: dict[str, Any]) -> dict[str, Any]:
    payment = payload.get("payload")
    if not isinstance(payment, dict):
        return {}
    payment_block = payment.get("payment")
    if not isinstance(payment_block, dict):
        return {}
    entity = payment_block.get("entity")
    if not isinstance(entity, dict):
        return {}
    return entity


def _cashfree_payment_entity(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return {}
    payment = data.get("payment")
    if not isinstance(payment, dict):
        return {}
    return payment


def _cashfree_order_entity(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return {}
    order = data.get("order")
    if not isinstance(order, dict):
        return {}
    return order


def _cashfree_customer_entity(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return {}
    customer = data.get("customer_details")
    if not isinstance(customer, dict):
        return {}
    return customer


def _cashfree_metadata(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, dict):
        return {}
    metadata = data.get("metadata")
    if not isinstance(metadata, dict):
        return {}
    return metadata


def _phonepe_payment_entity(payload: dict[str, Any]) -> dict[str, Any]:
    payment = payload.get("payload")
    if not isinstance(payment, dict):
        return {}
    return payment


def _phonepe_meta_info(payment_entity: dict[str, Any]) -> dict[str, Any]:
    meta_info = payment_entity.get("metaInfo")
    if not isinstance(meta_info, dict):
        return {}
    return meta_info


def _verify_razorpay_signature(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_signing_secret: str | None,
) -> str:
    import os
    secret = webhook_signing_secret or os.getenv("RAZORPAY_SANDBOX_WEBHOOK_SECRET")
    if not secret:
        return "not_verified_contract_mock"
    signature = _header_value(headers or {}, RAZORPAY_SIGNATURE_HEADER)
    if not signature:
        return "not_verified_contract_mock"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(signature, expected_signature):
        return "verified_contract_fixture"
    return "not_verified_contract_mock"


def _verify_cashfree_signature(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_signing_secret: str | None,
) -> str:
    import os
    secret = webhook_signing_secret or os.getenv("CASHFREE_SANDBOX_WEBHOOK_SECRET")
    if not secret:
        return "not_verified_contract_mock"
    signature = _header_value(headers or {}, CASHFREE_SIGNATURE_HEADER)
    if not signature:
        return "not_verified_contract_mock"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(signature, expected_signature):
        return "verified_contract_fixture"
    return "not_verified_contract_mock"


def _normalize_cashfree_event_type(payload: dict[str, Any]) -> str:
    raw_type = str(payload.get("type") or "").strip().upper()
    if raw_type == "PAYMENT_SUCCESS_WEBHOOK":
        return "payment.captured"
    if raw_type == "PAYMENT_FAILED_WEBHOOK":
        return "payment.failed"
    return raw_type.strip().lower()


def _verify_phonepe_signature(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_signing_secret: str | None,
) -> str:
    import os
    secret = webhook_signing_secret or os.getenv("PHONEPE_SANDBOX_SALT_KEY")
    if not secret:
        return "not_verified_contract_mock"
    signature = _header_value(headers or {}, PHONEPE_SIGNATURE_HEADER)
    if not signature:
        return "not_verified_contract_mock"
    if "###" not in signature:
        return "not_verified_contract_mock"
    digest, salt_index = signature.split("###", 1)
    if not salt_index.strip():
        return "not_verified_contract_mock"
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    body_b64 = base64.b64encode(body.encode("utf-8")).decode("ascii")
    expected_signature = hashlib.sha256(f"{body_b64}{PHONEPE_WEBHOOK_PATH}{secret}".encode("utf-8")).hexdigest()
    if hmac.compare_digest(digest.strip(), expected_signature):
        return "verified_contract_fixture"
    return "not_verified_contract_mock"


def _normalize_phonepe_event_type(payload: dict[str, Any]) -> str:
    raw_event = str(payload.get("event") or "").strip().lower()
    if raw_event == "checkout.order.completed":
        return "payment.captured"
    if raw_event == "checkout.order.failed":
        return "payment.failed"
    return raw_event


def _header_value(headers: Mapping[str, Any], expected_name: str) -> str:
    for key, value in headers.items():
        if str(key).strip().lower() == expected_name:
            return str(value).strip()
    return ""


def _date_from_timestamp(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).date()
    if isinstance(value, str) and value.strip():
        stripped = value.strip()
        if stripped.isdigit():
            return datetime.fromtimestamp(int(stripped), tz=timezone.utc).date()
        try:
            return date.fromisoformat(stripped)
        except ValueError:
            return datetime.fromisoformat(stripped.replace("Z", "+00:00")).date()
    return None
