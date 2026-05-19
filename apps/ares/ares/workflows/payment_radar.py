"""Payment radar workflow."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Invoice, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository


@dataclass(frozen=True)
class PaymentPriority:
    invoice: Invoice
    days_overdue: int
    risk_score: float
    reminder_draft: str


def _days_overdue(invoice: Invoice, today: date) -> int:
    if not invoice.due_date:
        return 0
    return max((today - invoice.due_date).days, 0)


def _draft(invoice: Invoice, days: int, repository: BusinessRepository | None = None) -> str:
    customer = invoice.customer_id or "customer"
    memories = [] if repository is None else [m for m in repository.list_memories() if m.subject_id == invoice.customer_id]
    soft_tone = any("soft" in m.content.lower() or "gently" in m.content.lower() for m in memories)
    if days <= 0:
        return f"Namaste {customer} ji, invoice {invoice.invoice_number} ka payment due hai. Kindly update expected date."
    prefix = "Gentle reminder" if soft_tone else f"Namaste {customer} ji"
    return f"{prefix}, invoice {invoice.invoice_number} ka payment {days} din overdue hai. Please payment status confirm karein."


def analyze_payment_radar(repository: BusinessRepository, *, today: date | None = None) -> dict:
    """Analyze outstanding payments without creating side effects."""
    today = today or date.today()
    priorities: list[PaymentPriority] = []
    for invoice in repository.get_outstanding():
        days = _days_overdue(invoice, today)
        risk = float(invoice.amount) + (days * 1000)
        priorities.append(PaymentPriority(invoice, days, risk, _draft(invoice, days, repository)))
    priorities.sort(key=lambda item: item.risk_score, reverse=True)
    return {
        "total_outstanding": sum(item.invoice.amount for item in priorities),
        "overdue_count": sum(1 for item in priorities if item.days_overdue > 0),
        "priorities": [
            {
                "invoice_id": item.invoice.id,
                "customer_id": item.invoice.customer_id,
                "amount": item.invoice.amount,
                "days_overdue": item.days_overdue,
                "risk_score": item.risk_score,
                "reminder_draft": item.reminder_draft,
            }
            for item in priorities
        ],
    }


def create_payment_reminder_approvals(
    repository: BusinessRepository,
    approvals: ApprovalService,
    *,
    client_id: str,
    priorities: list[dict],
) -> list:
    """Create idempotent approval requests for the analyzed priorities."""
    created = []
    invoices = {invoice.id: invoice for invoice in repository.get_outstanding()}
    for item in priorities[:10]:
        invoice = invoices.get(item["invoice_id"])
        if invoice is None:
            continue
        created.append(
            approvals.create_approval_request(
                client_id=client_id,
                action_type="send_customer_message",
                proposed_action=f"Send payment reminder for invoice {invoice.invoice_number}",
                data={
                    "customer": invoice.customer_id,
                    "invoice_id": invoice.id,
                    "draft": item["reminder_draft"],
                    "amount": invoice.amount,
                },
                reason="Ares can draft reminders, but customer-facing messages require approval.",
                source="payment_radar",
                confidence=0.9,
                risk_level=RiskLevel.medium if item["days_overdue"] < 30 else RiskLevel.high,
                dedupe_key=f"payment_reminder:{invoice.id}",
            )
        )
    return created


def run_payment_radar(
    repository: BusinessRepository,
    approvals: ApprovalService,
    *,
    client_id: str,
    today: date | None = None,
    create_approvals: bool = True,
) -> dict:
    payload = analyze_payment_radar(repository, today=today)
    if create_approvals:
        approvals_created = create_payment_reminder_approvals(
            repository,
            approvals,
            client_id=client_id,
            priorities=payload["priorities"],
        )
        payload["approvals_created"] = len(approvals_created)
    else:
        payload["approvals_created"] = 0
    return payload
