"""Local e-way bill draft contract."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_mapping_token

LOCAL_EWAY_LIMITATION = "Local e-way bill draft only; no NIC e-way bill API call or generation occurred."


def prepare_eway_bill_draft(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    invoice_id: str,
    seller_gstin: str,
    dispatch: dict,
    requested_by: str,
) -> dict:
    batch_id = f"eway_{stable_mapping_token({'client_id': client_id, 'invoice_id': invoice_id, 'seller_gstin': seller_gstin, 'dispatch': dispatch})}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="block_dispatch",
        proposed_action=f"Prepare e-way bill draft for invoice {invoice_id}",
        data={"batch_id": batch_id, "invoice_id": invoice_id, "seller_gstin": seller_gstin, "dispatch": dispatch},
        reason="E-way bill generation is statutory/dispatch-impacting and requires review.",
        source="eway_bill_contract",
        confidence=1.0,
        dedupe_key=f"eway:{batch_id}",
    )
    return {
        "status": "approval_required",
        "batch_id": batch_id,
        "approval_id": approval.id,
        "invoice_id": invoice_id,
        "audit": {"requested_by": requested_by, "nic_api_called": False, "limitation": LOCAL_EWAY_LIMITATION},
    }
