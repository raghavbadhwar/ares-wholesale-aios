"""Local ITC reconciliation contract."""

from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.contract_keys import stable_mapping_token

LOCAL_ITC_LIMITATION = "Local ITC reconciliation contract only; no GST portal call or filing mutation occurred."


def reconcile_itc_2b(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    period: str,
    portal_entries: list[dict],
    requested_by: str,
) -> dict:
    batch_id = f"itc_{stable_mapping_token({'client_id': client_id, 'period': period, 'portal_entries': portal_entries})}"
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="modify_ledger",
        proposed_action=f"Review ITC reconciliation for {period}",
        data={"batch_id": batch_id, "period": period, "portal_entry_count": len(portal_entries)},
        reason="ITC reconciliation affects tax positions and requires review.",
        source="itc_reconciliation_contract",
        confidence=1.0,
        dedupe_key=f"itc:{batch_id}",
    )
    return {
        "status": "approval_required",
        "batch_id": batch_id,
        "approval_id": approval.id,
        "period": period,
        "portal_entry_count": len(portal_entries),
        "audit": {"requested_by": requested_by, "gst_portal_called": False, "limitation": LOCAL_ITC_LIMITATION},
    }
