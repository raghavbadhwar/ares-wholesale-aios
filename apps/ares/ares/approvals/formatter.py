"""Owner-facing approval formatting."""

from __future__ import annotations

from apps.ares.ares.data.models import ApprovalRequest


def format_approval(approval: ApprovalRequest) -> str:
    affected = approval.data.get("customer") or approval.data.get("supplier") or approval.data.get("staff") or "N/A"
    lines = [
        f"Approval needed: {approval.proposed_action}",
        f"Type: {approval.type}",
        f"Reason: {approval.reason or 'Not provided'}",
        f"Source: {approval.source or 'Ares'}",
        f"Confidence: {approval.confidence:.0%}",
        f"Risk: {approval.risk_level.value}",
        f"Affected: {affected}",
        "Options: Approve / Edit / Reject / Ask me later",
    ]
    return "\n".join(lines)


def format_approval_list(approvals: list[ApprovalRequest]) -> str:
    if not approvals:
        return "No pending approvals."
    return "\n\n".join(format_approval(approval) for approval in approvals)

