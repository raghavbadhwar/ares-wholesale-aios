"""Post-dated cheque tracking for collections discipline."""

from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import PostDatedCheque, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

DEPOSIT_REMINDER_WINDOW_DAYS = 2


def register_post_dated_cheque(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    party_id: str,
    amount: float,
    cheque_date: date,
    bank_name: str,
    cheque_number: str,
    status: str = "scheduled",
    deposit_date: date | None = None,
    bounce_reason: str | None = None,
    invoice_id: str | None = None,
) -> PostDatedCheque:
    cheque = PostDatedCheque(
        id=f"pdc_{uuid4().hex[:12]}",
        party_id=party_id,
        amount=float(amount),
        cheque_date=cheque_date,
        bank_name=bank_name,
        cheque_number=cheque_number,
        status=status,
        deposit_date=deposit_date,
        bounce_reason=bounce_reason,
        invoice_id=invoice_id,
    )
    repository.upsert_post_dated_cheque(cheque)
    if status == "bounced":
        approvals.create_approval_request(
            client_id=client_id,
            action_type="section_138_followup",
            proposed_action="Review bounced cheque and prepare Section 138 follow-up.",
            data={
                "party_id": party_id,
                "amount": float(amount),
                "cheque_number": cheque_number,
                "bank_name": bank_name,
                "cheque_date": cheque_date.isoformat(),
            },
            reason="Bounced cheque requires legal/commercial follow-up review.",
            source="pdc_tracker",
            confidence=0.95,
            risk_level=RiskLevel.high,
            dedupe_key=f"section_138:{party_id}:{cheque_number}",
        )
    return cheque


def analyze_pdc_tracker(repository: BusinessRepository, *, today: date | None = None) -> dict:
    current_day = today or date.today()
    scheduled = [item for item in repository.get_post_dated_cheques() if item.status == "scheduled"]
    upcoming = [
        item for item in scheduled if current_day <= item.cheque_date <= current_day + timedelta(days=DEPOSIT_REMINDER_WINDOW_DAYS)
    ]
    bounced = [item for item in repository.get_post_dated_cheques() if item.status == "bounced"]
    return {
        "upcoming_count": len(upcoming),
        "upcoming_amount": float(sum(item.amount for item in upcoming)),
        "upcoming": [
            {
                "pdc_id": item.id,
                "party_id": item.party_id,
                "amount": item.amount,
                "bank_name": item.bank_name,
                "cheque_number": item.cheque_number,
                "cheque_date": item.cheque_date.isoformat(),
            }
            for item in sorted(upcoming, key=lambda item: (item.cheque_date, item.party_id))
        ],
        "bounced_count": len(bounced),
    }


def create_pdc_approvals(
    repository: BusinessRepository,
    approvals: ApprovalService,
    *,
    client_id: str,
    pdc_summary: dict,
) -> list:
    created = []
    for item in pdc_summary["upcoming"]:
        created.append(
            approvals.create_approval_request(
                client_id=client_id,
                action_type="deposit_pdc_cheque",
                proposed_action=f"Deposit cheque {item['cheque_number']} for {item['party_id']}",
                data=item,
                reason="PDC cheque is due for deposit within the reminder window.",
                source="pdc_tracker",
                confidence=0.94,
                risk_level=RiskLevel.medium,
                dedupe_key=f"deposit_pdc:{item['pdc_id']}",
            )
        )
    return created
