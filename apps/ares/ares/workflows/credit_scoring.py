"""Local party credit scoring."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from apps.ares.ares.data.models import Customer, Invoice, Payment
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_CREDIT_SCORING_LIMITATION = (
    "Local party credit scoring only; no bureau, account-aggregator, or lender integration was called."
)
OPEN_STATUSES = {"open", "overdue", "due", "unpaid"}


def _customer_invoices(invoices: list[Invoice], customer: Customer) -> list[Invoice]:
    return [invoice for invoice in invoices if invoice.customer_id == customer.id]


def _customer_payments(payments: list[Payment], customer: Customer, start: date, end: date) -> list[Payment]:
    return [
        payment
        for payment in payments
        if payment.customer_id == customer.id and payment.date is not None and start <= payment.date <= end
    ]


def _exposure(invoices: list[Invoice]) -> tuple[float, float]:
    current = 0.0
    overdue = 0.0
    for invoice in invoices:
        status = invoice.status.strip().lower()
        if status not in OPEN_STATUSES:
            continue
        current += float(invoice.amount)
        if status == "overdue":
            overdue += float(invoice.amount)
    return round(current, 2), round(overdue, 2)


def _oldest_overdue_days(invoices: list[Invoice], as_of: date) -> int:
    days = [
        max((as_of - invoice.due_date).days, 0)
        for invoice in invoices
        if invoice.status.strip().lower() == "overdue" and invoice.due_date is not None
    ]
    return max(days, default=0)


def _credit_utilization(customer: Customer, current_exposure: float) -> float:
    if not customer.credit_limit:
        return 0.0
    return round((current_exposure / float(customer.credit_limit)) * 100, 2)


def _bounced_pdc_count(repository: BusinessRepository, customer: Customer) -> int:
    return sum(
        1
        for cheque in repository.get_post_dated_cheques()
        if cheque.party_id == customer.id and cheque.status.strip().lower() == "bounced"
    )


def _risk_band(score: int) -> str:
    if score < 50:
        return "high"
    if score < 80:
        return "medium"
    return "low"


def _recommended_action(band: str) -> str:
    return {
        "high": "Block fresh dispatch unless owner approves recovery or credit exception.",
        "medium": "Keep dispatch approval-gated and ask for expected payment date.",
        "low": "Continue normal dispatch with routine payment monitoring.",
    }[band]


def _score(
    *,
    overdue_amount: float,
    oldest_overdue_days: int,
    credit_utilization_percent: float,
    bounced_pdc_count: int,
) -> int:
    score = 100
    if overdue_amount > 0:
        score -= 25
    if oldest_overdue_days > 45:
        score -= 25
    elif oldest_overdue_days > 15:
        score -= 10
    if credit_utilization_percent > 100:
        score -= 20
    elif credit_utilization_percent > 80:
        score -= 10
    score -= min(bounced_pdc_count * 15, 30)
    return max(score, 0)


def build_party_credit_scores(
    *,
    repository: BusinessRepository,
    as_of: date,
    lookback_days: int = 90,
) -> dict[str, Any]:
    """Build deterministic local credit scores for customer parties."""
    lookback_start = as_of - timedelta(days=lookback_days)
    invoices = repository.get_invoices()
    payments = repository.get_payments()
    party_scores: list[dict[str, Any]] = []

    for customer in repository.get_customers():
        customer_invoices = _customer_invoices(invoices, customer)
        current_exposure, overdue_amount = _exposure(customer_invoices)
        oldest_days = _oldest_overdue_days(customer_invoices, as_of)
        utilization = _credit_utilization(customer, current_exposure)
        bounced_count = _bounced_pdc_count(repository, customer)
        reconciled_payments = round(
            sum(
                float(payment.amount)
                for payment in _customer_payments(payments, customer, lookback_start, as_of)
                if payment.status.strip().lower() == "reconciled"
            ),
            2,
        )
        score = _score(
            overdue_amount=overdue_amount,
            oldest_overdue_days=oldest_days,
            credit_utilization_percent=utilization,
            bounced_pdc_count=bounced_count,
        )
        band = _risk_band(score)
        party_scores.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "score": score,
                "risk_band": band,
                "current_exposure": current_exposure,
                "overdue_amount": overdue_amount,
                "oldest_overdue_days": oldest_days,
                "credit_utilization_percent": utilization,
                "bounced_pdc_count": bounced_count,
                "reconciled_payments_last_90_days": reconciled_payments,
                "recommended_action": _recommended_action(band),
            }
        )

    risk_rank = {"high": 0, "medium": 1, "low": 2}
    party_scores.sort(key=lambda row: (risk_rank[row["risk_band"]], row["score"], row["customer_name"]))
    return {
        "mode": "local_contract_mock",
        "as_of": as_of.isoformat(),
        "lookback_days": lookback_days,
        "summary": {
            "parties": len(party_scores),
            "high_risk": sum(1 for row in party_scores if row["risk_band"] == "high"),
            "medium_risk": sum(1 for row in party_scores if row["risk_band"] == "medium"),
            "low_risk": sum(1 for row in party_scores if row["risk_band"] == "low"),
            "total_exposure": round(sum(float(row["current_exposure"]) for row in party_scores), 2),
            "overdue_exposure": round(sum(float(row["overdue_amount"]) for row in party_scores), 2),
        },
        "party_scores": party_scores,
        "audit": {
            "external_credit_bureau_called": False,
            "account_aggregator_called": False,
            "lender_score_generated": False,
            "limitation": LOCAL_CREDIT_SCORING_LIMITATION,
        },
    }
