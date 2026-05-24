"""Local GSTR-1 return preparation contract."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_contract_token

LOCAL_GSTR1_LIMITATION = "Local GSTR-1 draft only; no GSTN filing, upload, or statutory submission was performed."


def prepare_gstr1_return(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    period: str,
    seller_gstin: str,
    requested_by: str,
) -> dict:
    invoices = repository.get_invoices()
    batch_id = f"gstr1_{stable_contract_token(client_id, period, seller_gstin, [item.id for item in invoices])}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="modify_ledger",
        proposed_action=f"Prepare GSTR-1 draft for {period}",
        data={"batch_id": batch_id, "period": period, "seller_gstin": seller_gstin, "invoice_ids": [item.id for item in invoices]},
        reason="GST return preparation requires accountant/owner review before filing.",
        source="gstr1_contract",
        confidence=1.0,
        dedupe_key=f"gstr1:{batch_id}",
    )
    return {
        "status": "approval_required",
        "batch_id": batch_id,
        "approval_id": approval.id,
        "period": period,
        "seller_gstin": seller_gstin,
        "invoice_count": len(invoices),
        "audit": {"requested_by": requested_by, "gstn_api_called": False, "limitation": LOCAL_GSTR1_LIMITATION},
    }
