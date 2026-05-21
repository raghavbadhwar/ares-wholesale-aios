"""Local GSTN API exchange contract."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

GSTN_API_CONTRACT_LIMITATION = (
    "Local GSTN API contract only; no GSTN, NIC, sandbox, production API, or statutory filing was called."
)

OPERATION_ENDPOINTS = {
    "gstr1_return_upload": "gstn.gstr1.upload",
    "gstr2b_pull": "gstn.gstr2b.pull",
    "gstin_validation": "gstn.gstin.validate",
    "einvoice_irn_generation": "nic.einvoice.irn.generate",
    "eway_bill_status": "nic.eway.status",
}
PERIOD_REQUIRED_OPERATIONS = {"gstr1_return_upload", "gstr2b_pull"}


def prepare_gstn_api_exchange_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    operation: str,
    gstin: str,
    requested_by: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Prepare an approval-gated local GSTN/NIC request contract."""
    operation_key = operation.strip().lower()
    request_id = f"gstn_req_{uuid4().hex[:12]}"
    audit = _audit(requested_by=requested_by, approval_required=False)
    validation_errors = _validation_errors(operation=operation_key, gstin=gstin, payload=payload)
    request = _request_contract(request_id=request_id, operation=operation_key, gstin=gstin, payload=payload)

    if validation_errors:
        result = {
            "mode": "local_contract_mock",
            "status": "validation_failed",
            "request": request,
            "validation_errors": validation_errors,
            "audit": audit,
        }
        _save_log(repository, client_id=client_id, result=result)
        return result

    audit = _audit(requested_by=requested_by, approval_required=True)
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="submit_gstn_api_request",
        proposed_action=f"Review local GSTN API contract for {operation_key}",
        data={
            "request": request,
            "validation_errors": [],
            "mode": "local_contract_mock",
        },
        reason="GSTN/NIC exchanges affect statutory records and must be approved before any real integration is used.",
        source="gstn_api",
        confidence=0.8,
        risk_level=RiskLevel.high,
        dedupe_key=f"gstn_api:{client_id}:{operation_key}:{request_id}",
    )
    result = {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "request": request,
        "validation_errors": [],
        "audit": audit,
    }
    _save_log(repository, client_id=client_id, result=result)
    return result


def _request_contract(*, request_id: str, operation: str, gstin: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "operation": operation,
        "endpoint_key": OPERATION_ENDPOINTS.get(operation, "unsupported"),
        "gstin": gstin.strip(),
        "payload_digest": _payload_digest(payload),
        "queue_policy": {
            "max_retries": 3,
            "retry_backoff": "manual_review_required",
            "fallback": "accountant_manual_portal_review",
        },
        "response_contract": {
            "expected_statuses": ["accepted", "rejected", "queued", "needs_manual_review"],
            "audit_log_required": True,
            "manual_fallback_required": True,
        },
    }


def _payload_digest(payload: dict[str, Any]) -> dict[str, Any]:
    digest: dict[str, Any] = {}
    if "period" in payload:
        digest["period"] = payload["period"]
    if "invoice_id" in payload:
        digest["invoice_id"] = payload["invoice_id"]
    if "sections" in payload and isinstance(payload["sections"], dict):
        digest["sections"] = dict(payload["sections"])
    if "document_number" in payload:
        digest["document_number"] = payload["document_number"]
    return digest


def _validation_errors(*, operation: str, gstin: str, payload: dict[str, Any]) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    if operation not in OPERATION_ENDPOINTS:
        errors.append({"code": "operation_unsupported", "field": "operation"})
    if not gstin.strip():
        errors.append({"code": "gstin_missing"})
    if operation in PERIOD_REQUIRED_OPERATIONS and not payload.get("period"):
        errors.append({"code": "period_missing", "field": "payload.period"})
    return errors


def _audit(*, requested_by: str, approval_required: bool) -> dict[str, Any]:
    return {
        "requested_by": requested_by,
        "approval_required": approval_required,
        "gstn_api_called": False,
        "nic_api_called": False,
        "sandbox_credentials_used": False,
        "statutory_filing_performed": False,
        "limitation": GSTN_API_CONTRACT_LIMITATION,
    }


def _save_log(repository: BusinessRepository, *, client_id: str, result: dict[str, Any]) -> None:
    request = result["request"]
    audit = result["audit"]
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_{uuid4().hex[:12]}",
            client_id=client_id,
            approval_id=result.get("approval_id"),
            action_type="gstn_api_contract_prepared",
            status=result["status"],
            result={
                "request_id": request["request_id"],
                "operation": request["operation"],
                "endpoint_key": request["endpoint_key"],
                "validation_errors": result["validation_errors"],
                "gstn_api_called": audit["gstn_api_called"],
                "nic_api_called": audit["nic_api_called"],
                "statutory_filing_performed": audit["statutory_filing_performed"],
                "limitation": audit["limitation"],
            },
        )
    )
