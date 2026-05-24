"""Local GSTN/GSP request and response contracts."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_mapping_token

GSTN_API_CONTRACT_LIMITATION = "Local GSTN API contract only; no GSTN/GSP/NIC network call or statutory filing was performed."
ENDPOINT_KEYS = {
    "gstr1_return_upload": "gstn.gstr1.upload",
    "gstr2b_pull": "gstn.gstr2b.pull",
}


def prepare_gstn_api_exchange_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    operation: str,
    gstin: str,
    requested_by: str,
    payload: dict,
) -> dict:
    digest = dict(payload)
    if operation == "gstr1_return_upload":
        digest.setdefault(
            "statutory_bundle",
            {
                "bundle_type": "gstr1_sales_tax_events",
                "period": payload.get("period"),
            },
        )
    endpoint_key = ENDPOINT_KEYS.get(operation, operation)
    request_id = f"gstn_{stable_mapping_token({'client_id': client_id, 'operation': operation, 'gstin': gstin, 'payload': payload})}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="submit_gstn_api_request",
        proposed_action=f"Prepare GSTN {operation} request for {gstin}",
        data={
            "mode": "local_contract_mock",
            "request": {
                "request_id": request_id,
                "operation": operation,
                "gstin": gstin,
                "endpoint_key": endpoint_key,
                "payload_digest": digest,
            },
        },
        reason="GSTN operations require deterministic contract checks and human review.",
        source="gstn_api_contract",
        confidence=1.0,
        dedupe_key=f"gstn:{request_id}",
    )
    return {
        "status": "approval_required",
        "approval_id": approval.id,
        "request": {
            "request_id": request_id,
            "operation": operation,
            "gstin": gstin,
            "endpoint_key": endpoint_key,
            "payload_digest": digest,
        },
        "audit": {
            "requested_by": requested_by,
            "approval_required": True,
            "gstn_api_called": False,
            "nic_api_called": False,
            "sandbox_credentials_used": False,
            "statutory_filing_performed": False,
            "limitation": GSTN_API_CONTRACT_LIMITATION,
        },
    }


def normalize_gstn_api_response_contract(
    *,
    repository: BusinessRepository,
    client_id: str,
    provider: str,
    request: dict,
    response_payload: dict,
) -> dict:
    response = response_payload.get("response", response_payload) if isinstance(response_payload, dict) else {}
    status = response.get("status") or response_payload.get("status") if isinstance(response_payload, dict) else None
    normalized_response = dict(response) if isinstance(response, dict) else {}
    if "reference_id" in normalized_response and "portal_reference" not in normalized_response:
        normalized_response["portal_reference"] = normalized_response["reference_id"]
    if "errors" in normalized_response and "validation_errors" not in normalized_response:
        normalized_response["validation_errors"] = normalized_response["errors"]
    normalized_status = status or "accepted"
    result = {
        "status": status or "accepted",
        "client_id": client_id,
        "provider": provider,
        "request": request,
        "response": normalized_response,
        "portal_reference": normalized_response.get("portal_reference"),
        "audit": {
            "provider": provider,
            "gstn_api_called": False,
            "nic_api_called": False,
            "gsp_api_called": False,
            "sandbox_response_processed": True,
            "manual_fallback_required": normalized_status in {"validation_failed", "needs_manual_review"},
            "statutory_filing_performed": False,
            "limitation": GSTN_API_CONTRACT_LIMITATION,
        },
    }
    repository.save_action_log(
        ActionExecutionLog(
            id="act_gstn_api_response_" + stable_mapping_token(
                {
                    "client_id": client_id,
                    "provider": provider,
                    "request_id": request.get("request_id"),
                    "status": normalized_status,
                    "response": normalized_response,
                }
            ),
            client_id=client_id,
            action_type="gstn_api_response_normalized",
            status=normalized_status,
            result=result,
        )
    )
    return result
