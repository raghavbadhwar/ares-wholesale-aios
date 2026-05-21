"""Local collections dashboard aggregation."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.ares.ares.data.models import ApprovalStatus, PostDatedCheque
from apps.ares.ares.data.repository import BusinessRepository
from apps.ares.ares.workflows.credit_scoring import build_party_credit_scores

LOCAL_COLLECTIONS_DASHBOARD_LIMITATION = (
    "Local collections dashboard only; no live CRM, WhatsApp automation, or bank integration was called."
)


def _pdc_action_row(cheque: PostDatedCheque, as_of: date) -> dict[str, Any] | None:
    status = cheque.status.strip().lower()
    if status == "bounced":
        code = "pdc_bounced"
    elif status in {"scheduled", "deposited"} and cheque.cheque_date <= as_of:
        code = "pdc_due"
    else:
        return None
    return {
        "pdc_id": cheque.id,
        "party_id": cheque.party_id,
        "amount": float(cheque.amount),
        "cheque_date": cheque.cheque_date.isoformat(),
        "status": cheque.status,
        "code": code,
    }


def _pdc_actions(repository: BusinessRepository, as_of: date) -> list[dict[str, Any]]:
    rows = [
        row
        for cheque in repository.get_post_dated_cheques()
        if (row := _pdc_action_row(cheque, as_of)) is not None
    ]
    code_rank = {"pdc_bounced": 0, "pdc_due": 1}
    rows.sort(key=lambda row: (code_rank[row["code"]], row["cheque_date"], row["party_id"]))
    return rows


def _pending_reminders(repository: BusinessRepository) -> list[dict[str, Any]]:
    rows = []
    for approval in repository.list_pending_approvals():
        if approval.status != ApprovalStatus.pending or approval.type != "send_customer_message":
            continue
        if approval.source not in {"payment_radar", "collections_dashboard", "pdc_tracker"}:
            continue
        rows.append(
            {
                "approval_id": approval.id,
                "customer_id": approval.data.get("customer"),
                "invoice_id": approval.data.get("invoice_id"),
            }
        )
    rows.sort(key=lambda row: (str(row["customer_id"]), str(row["invoice_id"]), row["approval_id"]))
    return rows


def _priority_for(row: dict[str, Any], *, pdc_risk_count: int, pending_reminder_count: int) -> str:
    if row["risk_band"] == "high" or row["oldest_overdue_days"] > 30 or pdc_risk_count > 0:
        return "urgent"
    if row["overdue_amount"] > 0 or pending_reminder_count > 0:
        return "watch"
    return "routine"


def build_collections_dashboard(
    *,
    repository: BusinessRepository,
    as_of: date,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Build a local collections dashboard from dues, PDCs, reminders, and credit scores."""
    credit = build_party_credit_scores(repository=repository, as_of=as_of, lookback_days=lookback_days)
    pdc_actions = _pdc_actions(repository, as_of)
    bounced_counts: dict[str, int] = {}
    for action in pdc_actions:
        if action["code"] == "pdc_bounced":
            bounced_counts[action["party_id"]] = bounced_counts.get(action["party_id"], 0) + 1

    pending_reminders = _pending_reminders(repository)
    reminder_counts: dict[str, int] = {}
    for reminder in pending_reminders:
        customer_id = str(reminder["customer_id"])
        reminder_counts[customer_id] = reminder_counts.get(customer_id, 0) + 1

    priority_queue: list[dict[str, Any]] = []
    for score in credit["party_scores"]:
        if score["current_exposure"] <= 0 and score["overdue_amount"] <= 0:
            continue
        pdc_risk_count = bounced_counts.get(score["customer_id"], 0)
        pending_reminder_count = reminder_counts.get(score["customer_id"], 0)
        priority_queue.append(
            {
                "customer_id": score["customer_id"],
                "customer_name": score["customer_name"],
                "current_exposure": score["current_exposure"],
                "overdue_amount": score["overdue_amount"],
                "oldest_overdue_days": score["oldest_overdue_days"],
                "credit_score": score["score"],
                "risk_band": score["risk_band"],
                "pdc_risk_count": pdc_risk_count,
                "pending_reminder_count": pending_reminder_count,
                "collection_priority": _priority_for(score, pdc_risk_count=pdc_risk_count, pending_reminder_count=pending_reminder_count),
                "recommended_action": score["recommended_action"],
            }
        )

    priority_rank = {"urgent": 0, "watch": 1, "routine": 2}
    priority_queue.sort(
        key=lambda row: (
            priority_rank[row["collection_priority"]],
            -float(row["overdue_amount"]),
            row["credit_score"],
            row["customer_name"],
        )
    )
    return {
        "mode": "local_contract_mock",
        "as_of": as_of.isoformat(),
        "lookback_days": lookback_days,
        "summary": {
            "parties_with_dues": len(priority_queue),
            "total_outstanding": credit["summary"]["total_exposure"],
            "overdue_outstanding": credit["summary"]["overdue_exposure"],
            "high_risk_parties": credit["summary"]["high_risk"],
            "pending_reminders": len(pending_reminders),
            "pdc_actions": len(pdc_actions),
        },
        "priority_queue": priority_queue,
        "pdc_actions": pdc_actions,
        "pending_reminders": pending_reminders,
        "audit": {
            "external_crm_called": False,
            "whatsapp_automation_performed": False,
            "external_bank_feed_called": False,
            "limitation": LOCAL_COLLECTIONS_DASHBOARD_LIMITATION,
        },
    }
