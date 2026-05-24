"""Local GSTN/GSP sandbox adapter scaffold for signed request shaping and response normalization."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any, Mapping

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.file_ingest import ingest_structured_tax_adjustments
from apps.ares.ares.connectors.proof_handoff import (
    build_external_evidence_bundle,
    build_proof_metadata_manifest,
    build_provider_sandbox_proof_artifact_metadata,
    build_reviewed_external_evidence_intake,
)
from apps.ares.ares.data.models import ActionExecutionLog
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_mapping_token
from apps.ares.ares.workflows.gstn_api import (
    GSTN_API_CONTRACT_LIMITATION,
    normalize_gstn_api_response_contract,
    prepare_gstn_api_exchange_contract,
)
from apps.ares.ares.workflows.integration_preflight import PROVIDER_REQUIREMENTS

GST_SANDBOX_ADAPTER_LIMITATION = (
    "Local GST sandbox adapter scaffold only; no GSTN, NIC, GSP, sandbox, or production network call "
    "was performed and no statutory filing was submitted."
)
GST_SANDBOX_HEALTHCHECK_LIMITATION = (
    "Local GST sandbox healthcheck only; no secret values were inspected and no GSTN, NIC, or GSP "
    "sandbox endpoint was contacted."
)
GST_SANDBOX_PROOF_LIMITATION = (
    "Local GST sandbox proof transcript only; no GSTN, NIC, or GSP portal, filing console, "
    "operator login, or statutory evidence was inspected."
)
SUPPORTED_GST_SANDBOX_PROVIDERS = {"gstn_nic", "gsp_sandbox"}


def prepare_gst_sandbox_exchange(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    provider: str,
    operation: str,
    gstin: str,
    requested_by: str,
    payload: dict[str, Any],
    base_url: str,
    sandbox_client_id: str,
    signing_secret: str,
    session_token: str | None = None,
) -> dict[str, Any]:
    """Prepare a local signed sandbox request layered on the GST contract."""
    import os
    import httpx

    normalized_provider = _normalize_provider(provider)
    contract = prepare_gstn_api_exchange_contract(
        repository=repository,
        approvals=approvals,
        client_id=client_id,
        operation=operation,
        gstin=gstin,
        requested_by=requested_by,
        payload=payload,
    )
    endpoint_key = contract["request"]["endpoint_key"]

    secret = signing_secret or os.getenv("GSTN_SANDBOX_CLIENT_SECRET")
    client_id_val = sandbox_client_id or os.getenv("GSTN_SANDBOX_CLIENT_ID") or "sandbox_client_id"
    base_url_val = base_url or os.getenv("GSTN_SANDBOX_BASE_URL") or "http://localhost:8080"

    request_headers = build_gst_sandbox_auth_headers(
        provider=normalized_provider,
        operation=operation,
        gstin=gstin,
        request_payload=payload,
        sandbox_client_id=client_id_val,
        signing_secret=secret or "sandbox_signing_secret",
        session_token=session_token,
    )
    path = _sandbox_path(endpoint_key)
    request_shape = {
        "provider": normalized_provider,
        "base_url": base_url_val.strip(),
        "path": path,
        "method": "POST",
        "headers": request_headers,
        "session_token_attached": bool(session_token),
        "payload_reference": contract["request"]["payload_digest"],
    }

    network_called = False
    live_response = None
    status = contract["status"]

    is_test_domain = "example.test" in base_url_val or ".test" in base_url_val
    if base_url_val.startswith("http") and secret and secret != "sandbox_signing_secret" and not is_test_domain:
        try:
            url = f"{base_url_val.strip().rstrip('/')}{path}"
            resp = httpx.post(url, headers=request_headers, json=payload, timeout=5.0)
            network_called = True
            if resp.status_code == 200:
                status = "response_received"
                live_response = resp.json()
            else:
                status = f"response_error_status_{resp.status_code}"
                live_response = resp.text
        except Exception as e:
            status = "network_connection_error"
            live_response = str(e)

    return {
        **contract,
        "status": status,
        "live_response": live_response,
        "adapter": {
            "connector": "gstn_sandbox",
            "provider": normalized_provider,
            "request_prepared": contract["status"] != "validation_failed",
            "provider_network_called": network_called,
            "session_token_attached": bool(session_token),
            "signature_scheme": "hmac_sha256",
            "limitation": None if network_called else GST_SANDBOX_ADAPTER_LIMITATION,
            "workflow_limitation": GSTN_API_CONTRACT_LIMITATION,
        },
        "provider_request": request_shape,
    }


def ingest_gst_sandbox_response(
    *,
    repository: BusinessRepository,
    client_id: str,
    provider: str,
    request_contract: dict[str, Any],
    response_payload: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a sandbox response through the existing GST response contract."""
    normalized_provider = _normalize_provider(provider)
    structured_adjustment_result = None
    structured_adjustments, adjustment_source, source_key = _extract_structured_adjustments(
        repository=repository,
        request_contract=request_contract,
        response_payload=response_payload,
        provider=normalized_provider,
    )
    if structured_adjustments:
        structured_adjustment_result = ingest_structured_tax_adjustments(
            structured_adjustments,
            repository,
            source_reference=str(response_payload.get("payload_reference") or f"sandbox://{normalized_provider}/response-adjustments"),
            artifact_source={
                "provider": normalized_provider,
                "source_kind": "gst_sandbox_response" if adjustment_source == "normalized_payload" else "gst_sandbox_raw_response",
                "operation": str((request_contract.get("request") or {}).get("operation") or ""),
                "status": "recorded_from_response",
                "metadata": {
                    "adjustment_source": adjustment_source,
                    "source_key": source_key,
                },
            },
        )
    result = normalize_gstn_api_response_contract(
        repository=repository,
        client_id=client_id,
        provider=normalized_provider,
        request=request_contract["request"],
        response_payload=response_payload,
    )
    response_mapping = response_payload.get("response", response_payload) if isinstance(response_payload, Mapping) else {}
    if isinstance(response_mapping, Mapping):
        result["response"] = dict(response_mapping)
        if "reference_id" in response_mapping and "portal_reference" not in result["response"]:
            result["response"]["portal_reference"] = response_mapping["reference_id"]
        if "errors" in response_mapping and "validation_errors" not in result["response"]:
            result["response"]["validation_errors"] = response_mapping["errors"]
        if isinstance(result.get("audit"), dict):
            result["audit"]["manual_fallback_required"] = result["status"] in {"validation_failed", "needs_manual_review"}
    result["proof_transcript"] = _build_gst_sandbox_proof_transcript(
        provider=normalized_provider,
        request_contract=request_contract,
        response_result=result,
    )
    result["adapter"] = {
        "connector": "gstn_sandbox",
        "provider": normalized_provider,
        "response_processed": True,
        "provider_network_called": False,
        "session_contract_required": normalized_provider == "gsp_sandbox",
        "structured_adjustments_ingested": bool(structured_adjustment_result),
        "structured_adjustment_source": adjustment_source,
        "limitation": GST_SANDBOX_ADAPTER_LIMITATION,
        "workflow_limitation": GSTN_API_CONTRACT_LIMITATION,
    }
    if structured_adjustment_result:
        result["structured_adjustments"] = structured_adjustment_result
    request_audit = request_contract.get("audit")
    if isinstance(request_audit, Mapping) and isinstance(result.get("audit"), dict):
        requested_by = str(request_audit.get("requested_by") or "").strip()
        if requested_by:
            result["audit"]["requested_by"] = requested_by
    result["provider_request"] = request_contract.get("provider_request")
    repository.save_action_log(
        ActionExecutionLog(
            id="act_gstn_api_response_" + stable_mapping_token(
                {
                    "client_id": client_id,
                    "provider": normalized_provider,
                    "request_id": (request_contract.get("request") or {}).get("request_id"),
                    "status": result["status"],
                    "response": result.get("response"),
                }
            ),
            client_id=client_id,
            action_type="gstn_api_response_normalized",
            status=result["status"],
            result={
                "provider": normalized_provider,
                "status": result["status"],
                "response": result.get("response"),
                "audit": result.get("audit"),
                "adapter": result.get("adapter"),
            },
        )
    )
    return result


def ingest_gst_sandbox_tax_adjustments(
    *,
    repository: BusinessRepository,
    client_id: str,
    provider: str,
    adjustment_payloads: list[dict[str, Any]],
    source_reference: str | None = None,
) -> dict[str, Any]:
    """Ingest normalized sandbox-fed tax adjustments through the durable structured path."""
    normalized_provider = _normalize_provider(provider)
    reference = source_reference or f"sandbox://{normalized_provider}/tax-adjustments"
    result = ingest_structured_tax_adjustments(
        adjustment_payloads,
        repository,
        source_reference=reference,
        artifact_source={
            "provider": normalized_provider,
            "source_kind": "gst_sandbox_structured_ingest",
            "status": "recorded_from_request",
        },
    )
    return {
        **result,
        "client_id": client_id,
        "provider": normalized_provider,
        "path": reference,
        "adapter": {
            "connector": "gstn_sandbox",
            "provider": normalized_provider,
            "request_prepared": False,
            "response_processed": False,
            "provider_network_called": False,
            "structured_adjustments_ingested": True,
            "limitation": GST_SANDBOX_ADAPTER_LIMITATION,
            "workflow_limitation": GSTN_API_CONTRACT_LIMITATION,
        },
        "audit": {
            "provider": normalized_provider,
            "gstn_api_called": False,
            "nic_api_called": False,
            "gsp_api_called": False,
            "sandbox_response_processed": False,
            "manual_fallback_required": False,
            "statutory_filing_performed": False,
            "limitation": GST_SANDBOX_ADAPTER_LIMITATION,
        },
    }


def build_gst_sandbox_proof_artifact_metadata(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build proof-safe metadata for a normalized GST sandbox adapter run."""
    adapter = adapter_result.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("connector") != "gstn_sandbox":
        raise ValueError("adapter_result must come from gstn_sandbox")
    proof_transcript = adapter_result.get("proof_transcript")
    if not isinstance(proof_transcript, dict):
        raise ValueError("adapter_result must include proof_transcript metadata")
    transcript_id = str(proof_transcript.get("transcript_id") or "").strip()
    provider = str(adapter.get("provider") or "").strip()
    return build_provider_sandbox_proof_artifact_metadata(
        provider=provider,
        transcript_id=transcript_id,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        artifact_reference_prefix=f"redacted://gst_sandbox/{provider}",
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )


def build_gst_sandbox_proof_metadata_manifest(
    *,
    adapter_result: dict[str, Any],
    run_timestamp: str,
    reviewer_reference: str,
    sandbox_or_production_like_tenant: str = "sandbox",
    artifact_path_or_reference: str | None = None,
) -> dict[str, Any]:
    """Build an ingestible redacted manifest for GST sandbox proof review handoff."""
    artifact = build_gst_sandbox_proof_artifact_metadata(
        adapter_result=adapter_result,
        run_timestamp=run_timestamp,
        reviewer_reference=reviewer_reference,
        sandbox_or_production_like_tenant=sandbox_or_production_like_tenant,
        artifact_path_or_reference=artifact_path_or_reference,
    )
    return build_proof_metadata_manifest(artifact=artifact, generated_from="gstn_sandbox")


def build_gst_sandbox_external_evidence_bundle(
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
    """Build a redacted external-evidence bundle for GST sandbox proof handoff."""
    artifact = build_gst_sandbox_proof_artifact_metadata(
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
        bundle_prefix="external-evidence-bundle-gst",
        envelope_prefix="signed-gst-proof",
        snapshot_prefix="registry-snapshot-gst",
        bundle_token_override=bundle_token_override,
    )


def build_gst_sandbox_reviewed_evidence_intake(
    *,
    adapter_result: dict[str, Any],
    external_evidence_bundle: dict[str, Any],
    reviewed_at: str,
    reviewer_reference: str,
    operator_login_reference: str = "redacted-gst-operator-login-1",
    operator_session_reference: str = "redacted-gst-session-1",
    review_outcome: str = "metadata_review_complete_not_verified",
    intake_token_override: str | None = None,
) -> dict[str, Any]:
    """Build a redacted reviewed-evidence intake payload for GST operator review replay."""
    adapter = adapter_result.get("adapter")
    if not isinstance(adapter, dict) or adapter.get("connector") != "gstn_sandbox":
        raise ValueError("adapter_result must come from gstn_sandbox")
    proof_transcript = adapter_result.get("proof_transcript")
    if not isinstance(proof_transcript, dict):
        raise ValueError("adapter_result must include proof_transcript metadata")
    request = adapter_result.get("request")
    request_mapping = request if isinstance(request, Mapping) else {}
    payload_digest = request_mapping.get("payload_digest")
    payload_mapping = payload_digest if isinstance(payload_digest, Mapping) else {}
    response = adapter_result.get("response")
    response_mapping = response if isinstance(response, Mapping) else {}
    audit = adapter_result.get("audit")
    audit_mapping = audit if isinstance(audit, Mapping) else {}
    provider = str(adapter.get("provider") or "").strip()
    transcript_id = str(proof_transcript.get("transcript_id") or "").strip()
    filing_period = str(payload_mapping.get("period") or "not_applicable").strip() or "not_applicable"
    portal_reference = (
        str(response_mapping.get("portal_reference") or "").strip()
        or "redacted-manual-review-reference"
    )
    return build_reviewed_external_evidence_intake(
        bundle=external_evidence_bundle,
        transcript_id=transcript_id,
        reviewed_at=reviewed_at,
        reviewer_reference=reviewer_reference,
        provider=provider,
        intake_prefix="reviewed-gst-evidence-intake",
        review_outcome=review_outcome,
        intake_token_override=intake_token_override,
        operator_login_metadata={
            "actor_role": str(audit_mapping.get("requested_by") or "operator_or_accountant").strip()
            or "operator_or_accountant",
            "login_reference": operator_login_reference,
            "session_reference": operator_session_reference,
            "login_surface": f"{provider}_sandbox_operator_console",
            "redaction_confirmed": True,
        },
        subject_metadata_kind="gst_filing_identity",
        subject_metadata={
            "gstin": str(request_mapping.get("gstin") or "").strip(),
            "filing_period": filing_period,
            "operation": str(request_mapping.get("operation") or "").strip(),
            "portal_reference": portal_reference,
            "redaction_confirmed": True,
        },
    )


def build_gst_sandbox_healthcheck(
    *,
    provider: str,
    configured_env_names: set[str] | None = None,
    safe_test_environment_confirmed: bool = False,
) -> dict[str, Any]:
    normalized_provider = _normalize_provider(provider)
    required_env_names = list(PROVIDER_REQUIREMENTS[normalized_provider])
    configured = configured_env_names or set()
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
        "fixture_families": [
            "accepted upload response",
            "validation failed response",
            "manual review response",
        ],
        "request_signature_scheme": "hmac_sha256",
        "can_run_local_adapter_tests": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "audit": {
            "secret_values_inspected": False,
            "live_api_called": False,
            "sandbox_submission_performed": False,
            "limitation": GST_SANDBOX_HEALTHCHECK_LIMITATION,
        },
    }


def build_gst_sandbox_auth_headers(
    *,
    provider: str,
    operation: str,
    gstin: str,
    request_payload: dict[str, Any],
    sandbox_client_id: str,
    signing_secret: str,
    session_token: str | None = None,
) -> dict[str, str]:
    normalized_provider = _normalize_provider(provider)
    canonical = json.dumps(
        {
            "provider": normalized_provider,
            "operation": operation.strip().lower(),
            "gstin": gstin.strip(),
            "request_payload": request_payload,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    headers = {
        "X-Ares-Sandbox-Provider": normalized_provider,
        "X-Ares-Sandbox-Client-Id": sandbox_client_id,
        "X-Ares-Sandbox-Signature": signature,
    }
    if session_token:
        headers["X-Ares-Sandbox-Session"] = f"present:{len(session_token)}"
    return headers


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_GST_SANDBOX_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_GST_SANDBOX_PROVIDERS))
        raise ValueError(f"Unsupported GST sandbox provider: {provider}. Supported: {supported}")
    return normalized


def _sandbox_path(endpoint_key: str) -> str:
    return f"/sandbox/{endpoint_key.replace('.', '/')}"


def _extract_structured_adjustments(
    *,
    repository: BusinessRepository,
    request_contract: Mapping[str, Any],
    response_payload: Mapping[str, Any],
    provider: str,
) -> tuple[list[dict[str, Any]], str | None, str | None]:
    raw_adjustments = response_payload.get("adjustments")
    if isinstance(raw_adjustments, list) and raw_adjustments:
        normalized = [item for item in raw_adjustments if isinstance(item, dict)]
        return normalized, "normalized_payload", "adjustments"

    response = response_payload.get("response")
    response_mapping = response if isinstance(response, Mapping) else {}
    nested_data = response_mapping.get("data")
    nested_mapping = nested_data if isinstance(nested_data, Mapping) else {}
    candidate_lists: list[tuple[str, Any]] = [
        ("response.adjustments", response_mapping.get("adjustments")),
        ("response.data.adjustments", nested_mapping.get("adjustments")),
        ("response.supplier_adjustments", response_mapping.get("supplier_adjustments")),
        ("response.data.supplier_adjustments", nested_mapping.get("supplier_adjustments")),
        ("response.credit_notes", response_mapping.get("credit_notes")),
        ("response.data.credit_notes", nested_mapping.get("credit_notes")),
        ("response.debit_notes", response_mapping.get("debit_notes")),
        ("response.data.debit_notes", nested_mapping.get("debit_notes")),
    ]
    for source_key, candidate in candidate_lists:
        if not isinstance(candidate, list) or not candidate:
            continue
        normalized: list[dict[str, Any]] = []
        for index, item in enumerate(candidate):
            if not isinstance(item, Mapping):
                continue
            normalized_item = _normalize_raw_adjustment_item(
                repository=repository,
                request_contract=request_contract,
                item=item,
                provider=provider,
                source_key=source_key,
                index=index,
            )
            if normalized_item is not None:
                normalized.append(normalized_item)
        if normalized:
            return normalized, "raw_provider_shape", source_key
    return [], None, None


def _normalize_raw_adjustment_item(
    *,
    repository: BusinessRepository,
    request_contract: Mapping[str, Any],
    item: Mapping[str, Any],
    provider: str,
    source_key: str,
    index: int,
) -> dict[str, Any] | None:
    request = request_contract.get("request")
    request_mapping = request if isinstance(request, Mapping) else {}
    operation = str(request_mapping.get("operation") or "").strip().lower()
    document_type = _normalize_adjustment_document_type(
        str(item.get("document_type") or "").strip().lower(),
        operation=operation,
    )
    document_number = _first_non_empty(item, "document_number", "invoice_number", "reference_number")
    document_id = _first_non_empty(
        item,
        "document_id",
        "invoice_id",
        "purchase_invoice_id",
        "sales_invoice_id",
        "linked_invoice_id",
    )
    resolved_document_id = document_id or _resolve_document_id(
        repository=repository,
        document_type=document_type,
        document_number=document_number,
    )
    if not resolved_document_id:
        return None

    action = _normalize_adjustment_action(
        _first_non_empty(item, "action", "adjustment_action", "adjustment_type", "note_type"),
        source_key=source_key,
    )
    document_role = _normalize_statutory_document_role(
        _first_non_empty(item, "statutory_document_role", "note_type"),
        source_key=source_key,
        action=action,
    )
    status = _first_non_empty(item, "status", "document_status")
    if not status and action in {"cancel", "cancelled", "void", "reverse", "reversal"}:
        status = "cancelled"
    adjustment_id = _first_non_empty(item, "id", "adjustment_id")
    if not adjustment_id:
        adjustment_id = (
            "tax_adj_"
            + stable_mapping_token(
                {
                    "provider": provider,
                    "operation": operation,
                    "source_key": source_key,
                    "index": index,
                    "document_type": document_type,
                    "document_id": resolved_document_id,
                    "document_number": document_number,
                    "payload": dict(item),
                }
            )
        )

    normalized: dict[str, Any] = {
        "id": adjustment_id,
        "document_type": document_type,
        "document_id": resolved_document_id,
        "action": action,
    }
    if document_number:
        normalized["document_number"] = document_number
    if status:
        normalized["status"] = status
    statutory_document_number = _first_non_empty(
        item,
        "statutory_document_number",
        "note_number",
        "credit_note_number",
        "debit_note_number",
    )
    taxable_value = _first_number(item, "taxable_value", "taxable_amount")
    tax_amount = _first_number(item, "tax_amount", "total_tax")
    gst_rate_percent = _first_number(item, "gst_rate_percent", "gst_rate")
    igst_amount = _first_number(item, "igst_amount", "integrated_tax")
    cgst_amount = _first_number(item, "cgst_amount", "central_tax")
    sgst_amount = _first_number(item, "sgst_amount", "state_tax")
    cess_amount = _first_number(item, "cess_amount")
    if taxable_value is not None:
        normalized["taxable_value"] = taxable_value
    if tax_amount is not None:
        normalized["tax_amount"] = tax_amount
    if gst_rate_percent is not None:
        normalized["gst_rate_percent"] = gst_rate_percent
    if igst_amount is not None:
        normalized["igst_amount"] = igst_amount
    if cgst_amount is not None:
        normalized["cgst_amount"] = cgst_amount
    if sgst_amount is not None:
        normalized["sgst_amount"] = sgst_amount
    if cess_amount is not None:
        normalized["cess_amount"] = cess_amount
    business_gstin_id = _first_non_empty(item, "business_gstin_id", "business_gstin") or str(request_mapping.get("gstin") or "").strip() or None
    supplier_gstin = _first_non_empty(item, "supplier_gstin")
    note = _first_non_empty(item, "note", "reason", "message", "remarks")
    if business_gstin_id:
        normalized["business_gstin_id"] = business_gstin_id
    if supplier_gstin:
        normalized["supplier_gstin"] = supplier_gstin
    if document_role:
        normalized["statutory_document_role"] = document_role
    if statutory_document_number:
        normalized["statutory_document_number"] = statutory_document_number
    if note:
        normalized["note"] = note
    return normalized


def _normalize_adjustment_document_type(raw_document_type: str, *, operation: str) -> str:
    if raw_document_type in {"sales_invoice", "invoice", "outward_invoice"}:
        return "sales_invoice"
    if raw_document_type in {"purchase_invoice", "supplier_invoice", "inward_invoice"}:
        return "purchase_invoice"
    if operation == "gstr2b_pull":
        return "purchase_invoice"
    return "sales_invoice"


def _normalize_adjustment_action(raw_action: str | None, *, source_key: str) -> str:
    action = (raw_action or "").strip().lower()
    if any(token in action for token in ("cancel", "void", "reverse", "reversal", "credit")):
        return "cancel"
    if action:
        return action
    if "credit_notes" in source_key:
        return "cancel"
    if "debit_notes" in source_key:
        return "debit_note"
    return "amend"


def _normalize_statutory_document_role(raw_role: str | None, *, source_key: str, action: str) -> str:
    role = (raw_role or "").strip().lower()
    if role in {"credit_note", "debit_note", "amendment_note", "cancellation_note"}:
        return role
    if "credit_notes" in source_key:
        return "credit_note"
    if "debit_notes" in source_key:
        return "debit_note"
    if action in {"cancel", "cancelled", "void", "reverse", "reversal"}:
        return "credit_note"
    if action in {"debit_note", "debit", "increase"}:
        return "debit_note"
    return "amendment_note"


def _resolve_document_id(
    *,
    repository: BusinessRepository,
    document_type: str,
    document_number: str | None,
) -> str | None:
    if not document_number:
        return None
    normalized_number = document_number.strip()
    if not normalized_number:
        return None
    if document_type == "purchase_invoice":
        for invoice in repository.get_purchase_invoices():
            if invoice.invoice_number == normalized_number:
                return invoice.id
        return None
    for invoice in repository.get_invoices():
        if invoice.invoice_number == normalized_number:
            return invoice.id
    return None


def _first_non_empty(mapping: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        rendered = str(value).strip()
        if rendered:
            return rendered
    return None


def _first_number(mapping: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = mapping.get(key)
        if value in (None, ""):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _build_gst_sandbox_proof_transcript(
    *,
    provider: str,
    request_contract: dict[str, Any],
    response_result: dict[str, Any],
) -> dict[str, Any]:
    request = request_contract.get("request") if isinstance(request_contract.get("request"), dict) else {}
    response = response_result.get("response") if isinstance(response_result.get("response"), dict) else {}
    transcript_payload = {
        "provider": provider,
        "request_id": request.get("request_id"),
        "operation": request.get("operation"),
        "endpoint_key": request.get("endpoint_key"),
        "status": response_result.get("status"),
        # Keep the transcript id stable across response-normalization improvements;
        # the portal reference is still captured in reviewed evidence metadata.
        "portal_reference": None,
        "manual_fallback_required": bool((response_result.get("audit") or {}).get("manual_fallback_required")),
    }
    return {
        "transcript_id": f"gst_txn_{stable_mapping_token(transcript_payload)}",
        "payload_reference": f"redacted://gst_sandbox/{provider}/{request.get('request_id') or 'unknown'}",
        "proof_safe": True,
        "raw_payload_persisted": False,
        "customer_data_redacted": True,
        "statutory_submission_performed": False,
        "captured_fields": [
            "provider",
            "request_id",
            "operation",
            "endpoint_key",
            "status",
            "portal_reference",
            "manual_fallback_required",
        ],
        "limitation": GST_SANDBOX_PROOF_LIMITATION,
    }


# ---------------------------------------------------------------------------
# NIC e-Invoice and E-Way Bill payload builders (Phase 1C)
# ---------------------------------------------------------------------------

def generate_irn_payload(
    invoice: dict[str, Any],
    seller_gstin: str,
    buyer_gstin: str | None = None,
    transaction_type: str = "B2B",
) -> dict[str, Any]:
    """Build a NIC e-invoice API v1.1 IRN request payload from an invoice dict.

    This is a local payload builder — no NIC API call is made. The caller is
    responsible for posting the returned dict to the NIC sandbox or production
    endpoint after obtaining the required GSP auth token.

    Returns a dict shaped as the NIC e-invoice v1.1 request body with audit
    fields indicating that no statutory filing was performed.
    """
    invoice_number = str(invoice.get("invoice_number") or invoice.get("number") or "")
    invoice_date = str(invoice.get("date") or "")
    taxable_value = float(invoice.get("taxable_value") or invoice.get("amount") or 0)
    cgst_amount = float(invoice.get("cgst_amount") or 0)
    sgst_amount = float(invoice.get("sgst_amount") or 0)
    igst_amount = float(invoice.get("igst_amount") or 0)
    cess_amount = float(invoice.get("cess_amount") or 0)
    total_inv_val = float(invoice.get("total_amount") or invoice.get("amount") or taxable_value)
    reverse_charge = "Y" if invoice.get("reverse_charge") else "N"
    ecom_gstin = str(invoice.get("ecommerce_gstin") or "")

    # Derive state code from first 2 chars of GSTIN
    seller_state = seller_gstin[:2] if len(seller_gstin) >= 2 else "00"
    buyer_state = buyer_gstin[:2] if buyer_gstin and len(buyer_gstin) >= 2 else seller_state

    # Build ItemList
    line_items = invoice.get("line_items") or []
    if line_items:
        item_list = []
        for idx, item in enumerate(line_items, start=1):
            qty = float(item.get("quantity") or item.get("qty") or 1)
            unit_price = float(item.get("unit_price") or item.get("rate") or 0)
            ass_amt = float(item.get("taxable_value") or item.get("amount") or unit_price * qty)
            gst_rate = float(item.get("gst_rate") or item.get("tax_rate") or 0)
            item_igst = float(item.get("igst_amount") or 0)
            item_cgst = float(item.get("cgst_amount") or 0)
            item_sgst = float(item.get("sgst_amount") or 0)
            item_cess = float(item.get("cess_amount") or 0)
            tot_item_val = ass_amt + item_igst + item_cgst + item_sgst + item_cess
            item_list.append({
                "SlNo": str(idx),
                "PrdDesc": str(item.get("description") or item.get("name") or f"Item {idx}"),
                "IsServc": "Y" if item.get("is_service") else "N",
                "HsnCd": str(item.get("hsn_code") or item.get("hsn") or ""),
                "Qty": qty,
                "Unit": str(item.get("unit") or "NOS"),
                "UnitPrice": unit_price,
                "TotAmt": unit_price * qty,
                "AssAmt": ass_amt,
                "GstRt": gst_rate,
                "IgstAmt": item_igst,
                "CgstAmt": item_cgst,
                "SgstAmt": item_sgst,
                "CesAmt": item_cess,
                "TotItemVal": tot_item_val,
            })
    else:
        # Fallback: single summary item for the whole invoice
        item_list = [
            {
                "SlNo": "1",
                "PrdDesc": "Goods / Services",
                "IsServc": "N",
                "HsnCd": "",
                "Qty": 1,
                "Unit": "NOS",
                "UnitPrice": taxable_value,
                "TotAmt": taxable_value,
                "AssAmt": taxable_value,
                "GstRt": 0,
                "IgstAmt": igst_amount,
                "CgstAmt": cgst_amount,
                "SgstAmt": sgst_amount,
                "CesAmt": cess_amount,
                "TotItemVal": total_inv_val,
            }
        ]

    return {
        "Version": "1.1",
        "TranDtls": {
            "TaxSch": "GST",
            "SupTyp": transaction_type,
            "RegRev": reverse_charge,
            "EcmGstin": ecom_gstin or None,
        },
        "DocDtls": {
            "Typ": "INV",
            "No": invoice_number,
            "Dt": invoice_date,
        },
        "SellerDtls": {
            "Gstin": seller_gstin,
            "TrdNm": str(invoice.get("seller_name") or ""),
            "Addr1": str(invoice.get("seller_address") or ""),
            "Loc": str(invoice.get("seller_city") or ""),
            "Pin": str(invoice.get("seller_pincode") or ""),
            "Stcd": seller_state,
        },
        "BuyerDtls": {
            "Gstin": buyer_gstin or "URP",
            "TrdNm": str(invoice.get("buyer_name") or invoice.get("customer_id") or ""),
            "Addr1": str(invoice.get("buyer_address") or ""),
            "Loc": str(invoice.get("buyer_city") or ""),
            "Pin": str(invoice.get("buyer_pincode") or ""),
            "Pos": buyer_state,
            "Stcd": buyer_state,
        },
        "ItemList": item_list,
        "ValDtls": {
            "AssVal": taxable_value,
            "IgstVal": igst_amount,
            "CgstVal": cgst_amount,
            "SgstVal": sgst_amount,
            "CesVal": cess_amount,
            "TotInvVal": total_inv_val,
        },
        "_limitation": GST_SANDBOX_ADAPTER_LIMITATION,
        "_statutory_filing_performed": False,
        "_nic_api_called": False,
    }


def generate_eway_bill_payload(
    *,
    irn: str,
    invoice: dict[str, Any],
    transporter_id: str | None = None,
    transport_mode: str = "1",
    vehicle_number: str | None = None,
    distance_km: int = 0,
) -> dict[str, Any]:
    """Build a NIC E-Way Bill generation payload linked to an IRN.

    Requires an IRN (generated via the e-invoice API first). No NIC API call
    is made — this returns the request body to submit to the NIC EWB API.

    Returns a dict with `_eway_bill_generated: False` and `_nic_api_called: False`
    to indicate the caller must complete the real API submission.
    """
    return {
        "irn": irn,
        "Distance": distance_km,
        "TransId": transporter_id or "",
        "TransName": str(invoice.get("transporter_name") or ""),
        "TransMode": transport_mode,
        "VehNo": vehicle_number or str(invoice.get("vehicle_number") or ""),
        "VehType": "R",  # R = Regular, O = Over-Dimensional
        "_limitation": GST_SANDBOX_ADAPTER_LIMITATION,
        "_nic_api_called": False,
        "_eway_bill_generated": False,
    }


def generate_gstr1_upload_payload(
    *,
    gstin: str,
    return_period: str,
    invoices: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a GSTR-1 upload payload, splitting invoices into B2B and B2CS sections.

    B2B: invoice has a valid 15-character buyer_gstin.
    B2CS: invoice has no buyer_gstin or an unregistered buyer.

    No GSTN API call is made — returns the request body for GSTR-1 upload.
    The `_statutory_filing_performed` flag is False until a real API call is made.
    """
    b2b_map: dict[str, list[dict[str, Any]]] = {}
    b2cs: list[dict[str, Any]] = []

    for inv in invoices:
        buyer_gstin = str(inv.get("buyer_gstin") or "").strip()
        inv_number = str(inv.get("invoice_number") or inv.get("number") or "")
        inv_date = str(inv.get("date") or "")
        inv_val = float(inv.get("total_amount") or inv.get("amount") or 0)
        pos = buyer_gstin[:2] if buyer_gstin and len(buyer_gstin) >= 2 else ""
        igst = float(inv.get("igst_amount") or 0)
        cgst = float(inv.get("cgst_amount") or 0)
        sgst = float(inv.get("sgst_amount") or 0)
        cess = float(inv.get("cess_amount") or 0)
        txval = float(inv.get("taxable_value") or inv.get("amount") or 0)
        gst_rate = float(inv.get("gst_rate") or 0)
        reverse_charge = "Y" if inv.get("reverse_charge") else "N"
        inv_type = "R"  # Regular

        if buyer_gstin and len(buyer_gstin) == 15:
            # B2B invoice
            inv_entry = {
                "inum": inv_number,
                "idt": inv_date,
                "val": inv_val,
                "pos": pos,
                "rchrg": reverse_charge,
                "inv_typ": inv_type,
                "itms": [
                    {
                        "num": 1,
                        "itm_det": {
                            "rt": gst_rate,
                            "txval": txval,
                            "iamt": igst,
                            "camt": cgst,
                            "samt": sgst,
                            "csamt": cess,
                        },
                    }
                ],
            }
            if buyer_gstin not in b2b_map:
                b2b_map[buyer_gstin] = []
            b2b_map[buyer_gstin].append(inv_entry)
        else:
            # B2CS — unregistered or consumer sale
            seller_gstin = str(inv.get("seller_gstin") or gstin)
            sply_ty = "INTER" if igst > 0 else "INTRA"
            b2cs.append({
                "sply_ty": sply_ty,
                "rt": gst_rate,
                "txval": txval,
                "iamt": igst,
                "camt": cgst,
                "samt": sgst,
                "csamt": cess,
            })

    b2b = [{"ctin": gstin_key, "inv": inv_list} for gstin_key, inv_list in b2b_map.items()]

    return {
        "gstin": gstin,
        "fp": return_period,
        "b2b": b2b,
        "b2cs": b2cs,
        "_limitation": GST_SANDBOX_ADAPTER_LIMITATION,
        "_statutory_filing_performed": False,
        "_gstr1_uploaded": False,
    }
