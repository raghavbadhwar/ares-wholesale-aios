from __future__ import annotations

from datetime import date

from apps.ares.ares.data.models import Customer, Invoice, Payment, PostDatedCheque
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.credit_scoring import build_party_credit_scores


def test_should_score_parties_from_local_exposure_overdue_payments_and_pdc_risk() -> None:
    repo = InMemoryRepository.from_records(
        customers=[
            Customer(id="cust_good", name="Good Retail", credit_limit=50000),
            Customer(id="cust_risk", name="Risk Retail", credit_limit=10000),
        ],
        invoices=[
            Invoice(id="inv_good", invoice_number="INV-GOOD", customer_id="cust_good", amount=10000, due_date=date(2026, 5, 15), status="paid"),
            Invoice(id="inv_risk_open", invoice_number="INV-RISK-1", customer_id="cust_risk", amount=8000, due_date=date(2026, 5, 30), status="open"),
            Invoice(id="inv_risk_old", invoice_number="INV-RISK-2", customer_id="cust_risk", amount=7000, due_date=date(2026, 4, 1), status="overdue"),
        ],
        payments=[
            Payment(id="pay_good", customer_id="cust_good", amount=10000, date=date(2026, 5, 14), mode="upi", status="reconciled"),
        ],
    )
    repo.upsert_post_dated_cheque(
        PostDatedCheque(
            id="pdc_risk",
            party_id="cust_risk",
            amount=5000,
            cheque_date=date(2026, 5, 10),
            bank_name="HDFC Bank",
            cheque_number="123456",
            status="bounced",
        )
    )

    scores = build_party_credit_scores(repository=repo, as_of=date(2026, 5, 21), lookback_days=90)

    assert scores["mode"] == "local_contract_mock"
    assert scores["summary"] == {
        "parties": 2,
        "high_risk": 1,
        "medium_risk": 0,
        "low_risk": 1,
        "total_exposure": 15000.0,
        "overdue_exposure": 7000.0,
    }
    assert scores["party_scores"][0] == {
        "customer_id": "cust_risk",
        "customer_name": "Risk Retail",
        "score": 15,
        "risk_band": "high",
        "current_exposure": 15000.0,
        "overdue_amount": 7000.0,
        "oldest_overdue_days": 50,
        "credit_utilization_percent": 150.0,
        "bounced_pdc_count": 1,
        "reconciled_payments_last_90_days": 0.0,
        "recommended_action": "Block fresh dispatch unless owner approves recovery or credit exception.",
    }
    assert scores["party_scores"][1]["customer_id"] == "cust_good"
    assert scores["party_scores"][1]["score"] == 100
    assert scores["party_scores"][1]["risk_band"] == "low"
    assert scores["audit"] == {
        "external_credit_bureau_called": False,
        "account_aggregator_called": False,
        "lender_score_generated": False,
        "limitation": "Local party credit scoring only; no bureau, account-aggregator, or lender integration was called.",
    }


def test_should_return_empty_credit_scores_without_customers() -> None:
    scores = build_party_credit_scores(repository=InMemoryRepository(), as_of=date(2026, 5, 21))

    assert scores["summary"]["parties"] == 0
    assert scores["party_scores"] == []
