"""Local supplier payment sandbox adapter scaffold for provider-shaped settlement payloads."""

from __future__ import annotations

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
)
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_mapping_token
from apps.ares.ares.workflows.supplier_payments import (
    LOCAL_SUPPLIER_PAYMENT_LIMITATION,
    ingest_supplier_payment_receipt,
)

SUPPLIER_PAYMENT_SANDBOX_ADAPTER_LIMITATION = (
    "Local supplier payment sandbox adapter scaffold only; no live bank API, UPI collect request, payout execution, "
    "webhook registration, or banking settlement was performed."
)
SUPPLIER_PAYMENT_SANDBOX_HEALTHCHECK_LIMITATION = (
    "Local supplier payment sandbox healthcheck only; no secret values were inspected and no provider network or "
    "sandbox webhook endpoint was contacted."
)
SUPPLIER_PAYMENT_SANDBOX_PROOF_LIMITATION = (
    "Local supplier payment sandbox proof transcript only; no live bank portal, payout console, or settlement "
    "evidence was inspected."
)
UPI_COLLECT_SIGNATURE_HEADER = "x-upi-signature"
UPI_COLLECT_SIGNATURE_SCHEME = "hmac_sha256"
BANK_TRANSFER_SIGNATURE_SCHEME = "fixture_verified"
SUPPLIER_PAYMENT_SANDBOX_PROVIDER_CONFIG = {
    "bank_transfer": {
        "signature_scheme": BANK_TRANSFER_SIGNATURE_SCHEME,
        "fixture_families": [
            "supplier settlement posted payload",
            "supplier settlement failed payload",
            "nested bank transfer settlement export payload",
        ],
    },
    "upi_collect": {
        "signature_scheme": UPI_COLLECT_SIGNATURE_SCHEME,
        "fixture_families": [
            "supplier UPI settlement success payload",
            "supplier UPI settlement failed payload",
            "root-level supplier UPI settlement payload",
        ],
    },
}
SUPPORTED_SUPPLIER_PAYMENT_SANDBOX_PROVIDERS = frozenset(SUPPLIER_PAYMENT_SANDBOX_PROVIDER_CONFIG)
SUCCESS_EVENT_TYPES = {"supplier_payment.settled", "settlement.posted", "payment.success"}
FAILURE_EVENT_TYPES = {"supplier_payment.failed", "settlement.failed", "payment.failed", "payment.reversed"}


def ingest_supplier_payment_sandbox_payload(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    provider: str,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None = None,
    webhook_signing_secret: str | None = None,
) -> dict[str, Any]:
    """Normalize a sandbox supplier-payment payload and route it into the local settlement contract."""
    normalized_provider = _normalize_provider(provider)
    if normalized_provider == "bank_transfer":
        normalized = _normalize_bank_transfer_payload(payload=payload)
    elif normalized_provider == "upi_collect":
        normalized = _normalize_upi_collect_payload(
            payload=payload,
            headers=headers,
            webhook_signing_secret=webhook_signing_secret,
        )
    else:  # pragma: no cover
        raise ValueError(f"Unsupported supplier payment sandbox provider: {provider}")

    signature_verified = normalized["receipt"]["signature_verification_status"] in {
        "verified",
        "verified_contract_fixture",
    }
    proof_transcript = _build_supplier_payment_proof_transcript(
        provider=normalized_provider,
        normalized_event_type=normalized["event_type"],
        payment_id=str(normalized["receipt"].get("external_event_id") or ""),
        payload_reference=normalized["provider_payload"]["payload_reference"],
        signature_verified=signature_verified,
    )

    if normalized["event_type"] in FAILURE_EVENT_TYPES:
        return {
            "mode": "local_contract_mock",
            "status": "ignored_non_success_event",
            "event_type": normalized["event_type"],
            "supplier_payment": None,
            "provider_payload": normalized["provider_payload"],
            "proof_transcript": proof_transcript,
            "adapter": {
                "connector": "supplier_payment_sandbox",
                "provider": normalized_provider,
                "signature_scheme": SUPPLIER_PAYMENT_SANDBOX_PROVIDER_CONFIG[normalized_provider]["signature_scheme"],
                "signature_verified": signature_verified,
                "normalized_event_type": normalized["event_type"],
                "live_webhook_received": False,
                "provider_api_called": False,
                "bank_execution_performed": False,
                "limitation": SUPPLIER_PAYMENT_SANDBOX_ADAPTER_LIMITATION,
                "workflow_limitation": LOCAL_SUPPLIER_PAYMENT_LIMITATION,
            },
            "audit": {
                "provider": normalized_provider,
                "live_webhook_received": False,
                "webhook_signature_verified": signature_verified,
                "provider_api_called": False,
                "bank_execution_performed": False,
                "supplier_payment_record_created": False,
                "limitation": LOCAL_SUPPLIER_PAYMENT_LIMITATION,
            },
        }

    workflow_result = ingest_supplier_payment_receipt(
        repository=repository,
        approvals=approvals,
        client_id=client_id,
        receipt=normalized["receipt"],
    )
    return {
        "mode": "local_contract_mock",
        "status": workflow_result["status"],
        "event_type": normalized["event_type"],
        "supplier_payment": workflow_result.get("supplier_payment", workflow_result),
        "provider_payload": normalized["provider_payload"],
        "proof_transcript": proof_transcript,
        "adapter": {
            "connector": "supplier_payment_sandbox",
            "provider": normalized_provider,
            "signature_scheme": SUPPLIER_PAYMENT_SANDBOX_PROVIDER_CONFIG[normalized_provider]["signature_scheme"],
            "signature_verified": signature_verified,
            "normalized_event_type": normalized["event_type"],
            "live_webhook_received": False,
            "provider_api_called": False,
            "bank_execution_performed": False,
            "limitation": SUPPLIER_PAYMENT_SANDBOX_ADAPTER_LIMITATION,
            "workflow_limitation": LOCAL_SUPPLIER_PAYMENT_LIMITATION,
        },
        "audit": {
            "provider": normalized_provider,
            "live_webhook_received": False,
            "webhook_signature_verified": signature_verified,
            "provider_api_called": False,
            "bank_execution_performed": False,
            "supplier_payment_record_created": normalized["event_type"] in SUCCESS_EVENT_TYPES,
            "limitation": LOCAL_SUPPLIER_PAYMENT_LIMITATION,
        },
    }


def build_supplier_payment_sandbox_healthcheck(
    *,
    provider: str,
    configured_env_names: set[str] | None = None,
    safe_test_environment_confirmed: bool = False,
) -> dict[str, Any]:
    """Build an adapter-facing local healthcheck gate without contacting any provider."""
    normalized_provider = _normalize_provider(provider)
    configured = configured_env_names or set()
    required_env_names = (
        ["SUPPLIER_BANK_SANDBOX_TENANT_ID"]
        if normalized_provider == "bank_transfer"
        else ["SUPPLIER_UPI_SANDBOX_WEBHOOK_SECRET"]
    )
    missing_env_names = [name for name in required_env_names if name not in configured]
    blocked_reasons: list[str] = []
    if missing_env_names:
        blocked_reasons.append(f"missing sandbox environment names: {', '.join(missing_env_names)}")
    if not safe_test_environment_confirmed:
        blocked_reasons.append(f"safe non-production sandbox tenant not confirmed for {normalized_provider}")
    return {
        "mode": "local_contract_mock",
        "provider": normalized_provider,
        "status": "ready_for_local_adapter_tests" if not blocked_reasons else "blocked",
        "required_env_names": required_env_names,
        "missing_env_names": missing_env_names,
        "safe_test_environment_confirmed": safe_test_environment_confirmed,
        "fixture_families": list(SUPPLIER_PAYMENT_SANDBOX_PROVIDER_CONFIG[normalized_provider]["fixture_families"]),
        "webhook_signature_scheme": SUPPLIER_PAYMENT_SANDBOX_PROVIDER_CONFIG[normalized_provider]["signature_scheme"],
        "can_run_local_adapter_tests": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": SUPPLIER_PAYMENT_SANDBOX_HEALTHCHECK_LIMITATION,
        },
    }


def build_supplier_payment_sandbox_proof_artifact_metadata(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    adapter = adapter_result.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("connector") != "supplier_payment_sandbox":
        raise ValueError("adapter_result must come from supplier_payment_sandbox")
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
        artifact_reference_prefix=f"redacted://supplier_payment/{provider}",
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )


def build_supplier_payment_sandbox_proof_metadata_manifest(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    artifact = build_supplier_payment_sandbox_proof_artifact_metadata(
        adapter_result=adapter_result,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )
    return build_proof_metadata_manifest(artifact=artifact, generated_from="supplier_payment_sandbox")


def build_supplier_payment_sandbox_external_evidence_bundle(
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
    artifact = build_supplier_payment_sandbox_proof_artifact_metadata(
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
        bundle_prefix="external-evidence-bundle-supplier-payment",
        envelope_prefix="signed-supplier-payment-proof",
        snapshot_prefix="registry-snapshot-supplier-payment",
        bundle_token_override=bundle_token_override,
    )


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_SUPPLIER_PAYMENT_SANDBOX_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_SUPPLIER_PAYMENT_SANDBOX_PROVIDERS))
        raise ValueError(f"Unsupported supplier payment sandbox provider: {provider}. Supported: {supported}")
    return normalized


def _build_supplier_payment_proof_transcript(
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
        "transcript_id": f"supplier_payment_txn_{stable_mapping_token(transcript_payload)}",
        "payload_reference": payload_reference,
        "proof_safe": True,
        "raw_payload_persisted": False,
        "supplier_data_redacted": True,
        "signature_verified": signature_verified,
        "captured_fields": [
            "provider",
            "normalized_event_type",
            "payment_id",
            "payload_reference",
            "signature_verified",
        ],
        "limitation": SUPPLIER_PAYMENT_SANDBOX_PROOF_LIMITATION,
    }


def _normalize_bank_transfer_payload(*, payload: dict[str, Any]) -> dict[str, Any]:
    settlement = _first_mapping(
        payload,
        ("settlement",),
        ("data", "settlement"),
        ("data", "transfer"),
        ("transfer",),
        ("payment",),
    )
    raw_status = _lower_or_none(
        _first_value(
            settlement,
            ("status",),
            ("state",),
            ("result",),
        )
        or _first_value(payload, ("status",), ("state",), ("result",))
    )
    event_type = _normalize_event_type(
        explicit_event_type=_first_text(payload, ("event",), ("type",)),
        raw_status=raw_status,
        success_default="settlement.posted",
        failure_default="settlement.failed",
    )
    paid_on = _date_from_iso_like(
        _first_value(
            settlement,
            ("settled_on",),
            ("settled_at",),
            ("value_date",),
            ("executed_at",),
        )
        or _first_value(payload, ("settled_on",), ("settled_at",), ("event_time",))
    )
    payment_id = _first_text(
        settlement,
        ("id",),
        ("settlement_id",),
        ("payment_id",),
        ("transfer_id",),
        ("event_id",),
    ) or _first_text(payload, ("payment_id",), ("event_id",))
    amount = _coerce_amount(
        _first_value(
            settlement,
            ("amount",),
            ("gross_amount",),
            ("settled_amount",),
        )
    )
    if amount is None:
        amount_minor = _first_value(
            settlement,
            ("amount_minor",),
            ("amount_paise",),
        )
        if amount_minor is not None:
            amount = round(float(amount_minor) / 100.0, 2)
    receipt = {
        "supplier_id": _first_text(
            settlement,
            ("supplier_id",),
            ("beneficiary_id",),
            ("vendor_id",),
        ) or _first_text(payload, ("supplier_id",), ("beneficiary_id",), ("vendor_id",)),
        "purchase_invoice_id": _first_text(
            settlement,
            ("purchase_invoice_id",),
            ("invoice_id",),
            ("invoice_ref",),
            ("bill_id",),
        ) or _first_text(payload, ("purchase_invoice_id",), ("invoice_id",), ("invoice_ref",), ("bill_id",)),
        "amount": round(amount or _coerce_amount(_first_value(payload, ("amount",))) or 0, 2),
        "paid_on": paid_on.isoformat() if paid_on else None,
        "mode": "bank_transfer",
        "provider": "bank_transfer",
        "reference": _first_text(
            settlement,
            ("utr",),
            ("bank_reference",),
            ("rrn",),
            ("reference",),
            ("txn_ref",),
        ) or _first_text(payload, ("reference",), ("utr",), ("bank_reference",)) or payment_id,
        "external_event_id": payment_id or None,
        "source_event_type": event_type,
        "signature_verification_status": "verified_contract_fixture",
        "gateway_event": dict(payload),
    }
    provider_payload = {
        "provider": "bank_transfer",
        "event_type": event_type,
        "payment_id": payment_id or None,
        "payment_status": raw_status,
        "payload_reference": str(payload.get("payload_reference") or "").strip() or None,
        "contains_redacted_test_data": bool(payload.get("contains_redacted_test_data")),
    }
    return {"event_type": event_type, "receipt": receipt, "provider_payload": provider_payload}


def _normalize_upi_collect_payload(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_signing_secret: str | None,
) -> dict[str, Any]:
    data = _first_mapping(payload, ("data",), ("result",))
    payment = _first_mapping(
        payload,
        ("data", "payment"),
        ("data", "transaction"),
        ("payment",),
        ("result", "payment"),
        ("transaction",),
    )
    raw_status = _lower_or_none(
        _first_value(
            payment,
            ("status",),
            ("state",),
            ("result",),
        )
        or _first_value(payload, ("status",), ("state",), ("result",))
    )
    event_type = _normalize_event_type(
        explicit_event_type=_first_text(payload, ("type",), ("event",)),
        raw_status=raw_status,
        success_default="payment.success",
        failure_default="payment.failed",
    )
    paid_on = _date_from_iso_like(
        _first_value(
            payment,
            ("paid_at",),
            ("settled_at",),
            ("created_at",),
        )
        or _first_value(payload, ("event_time",), ("paid_at",), ("settled_at",))
    )
    payment_id = _first_text(
        payment,
        ("id",),
        ("payment_id",),
        ("transaction_id",),
    ) or _first_text(payload, ("payment_id",), ("transaction_id",))
    amount = _coerce_amount(
        _first_value(
            payment,
            ("amount",),
            ("amount_value",),
        )
    )
    if amount is None:
        amount_minor = _first_value(payment, ("amount_minor",), ("amount_paise",))
        if amount_minor is not None:
            amount = round(float(amount_minor) / 100.0, 2)
    receipt = {
        "supplier_id": _first_text(
            payment,
            ("supplier_id",),
            ("supplier",),
            ("merchant_supplier_id",),
        ) or _first_text(data, ("supplier_id",), ("supplier",)),
        "purchase_invoice_id": _first_text(
            payment,
            ("purchase_invoice_id",),
            ("invoice_id",),
            ("invoice_ref",),
        ) or _first_text(data, ("purchase_invoice_id",), ("invoice_id",), ("invoice_ref",)),
        "amount": round(amount or 0, 2),
        "paid_on": paid_on.isoformat() if paid_on else None,
        "mode": "upi_collect",
        "provider": "upi_collect",
        "reference": _first_text(
            payment,
            ("utr",),
            ("rrn",),
            ("bank_ref",),
            ("reference",),
        ) or payment_id,
        "external_event_id": payment_id or None,
        "source_event_type": event_type,
        "signature_verification_status": _verify_upi_collect_signature(
            payload=payload,
            headers=headers,
            webhook_signing_secret=webhook_signing_secret,
        ),
        "gateway_event": dict(payload),
    }
    provider_payload = {
        "provider": "upi_collect",
        "event_type": event_type,
        "payment_id": payment_id or None,
        "payment_status": raw_status,
        "payload_reference": str(payload.get("payload_reference") or "").strip() or None,
        "contains_redacted_test_data": bool(payload.get("contains_redacted_test_data")),
    }
    return {"event_type": event_type, "receipt": receipt, "provider_payload": provider_payload}


def _first_mapping(mapping: Mapping[str, Any], *paths: tuple[str, ...]) -> dict[str, Any]:
    for path in paths:
        value = _path_value(mapping, path)
        if isinstance(value, dict):
            return dict(value)
    return {}


def _first_value(mapping: Mapping[str, Any], *paths: tuple[str, ...]) -> Any:
    for path in paths:
        value = _path_value(mapping, path)
        if value is not None:
            return value
    return None


def _first_text(mapping: Mapping[str, Any], *paths: tuple[str, ...]) -> str | None:
    value = _first_value(mapping, *paths)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _path_value(mapping: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = mapping
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def _lower_or_none(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def _normalize_event_type(
    *,
    explicit_event_type: str | None,
    raw_status: str | None,
    success_default: str,
    failure_default: str,
) -> str:
    if explicit_event_type:
        return explicit_event_type.strip().lower()
    if raw_status in {"failed", "failure", "reversed", "reversal", "cancelled", "canceled", "declined"}:
        return failure_default
    if raw_status in {"posted", "settled", "success", "successful", "paid", "completed", "captured"}:
        return success_default
    return success_default


def _coerce_amount(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and not value.strip():
        return None
    return round(float(value), 2)


def _verify_upi_collect_signature(
    *,
    payload: dict[str, Any],
    headers: Mapping[str, Any] | None,
    webhook_signing_secret: str | None,
) -> str:
    import os
    secret = webhook_signing_secret or os.getenv("SUPPLIER_UPI_SANDBOX_WEBHOOK_SECRET")
    if not secret:
        return "not_verified_contract_mock"
    signature = _header_value(headers or {}, UPI_COLLECT_SIGNATURE_HEADER)
    if not signature:
        return "not_verified_contract_mock"
    canonical_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    expected = hmac.new(
        secret.encode("utf-8"),
        canonical_payload,
        hashlib.sha256,
    ).hexdigest()
    if hmac.compare_digest(signature.lower(), expected.lower()):
        return "verified_contract_fixture"
    return "not_verified_contract_mock"


def _header_value(headers: Mapping[str, Any], header_name: str) -> str | None:
    for key, value in headers.items():
        if str(key).strip().lower() == header_name.lower():
            return str(value).strip()
    return None


def _date_from_iso_like(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value.strip():
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(normalized).date()
        except ValueError:
            return date.fromisoformat(value.strip())
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc).date()
    return None
