from __future__ import annotations

from datetime import date

from apps.ares.ares.data.models import Customer, Invoice, Payment
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.retailer_segmentation import build_retailer_segmentation


def test_should_segment_retailers_by_value_credit_risk_and_dormancy() -> None:
    repo = InMemoryRepository.from_records(
        customers=[
            Customer(id="cust_star", name="Star Retail", credit_limit=100000),
            Customer(id="cust_risk", name="Risk Retail", credit_limit=12000),
            Customer(id="cust_dormant", name="Dormant Retail", credit_limit=5000),
        ],
        invoices=[
            Invoice(
                id="inv_star",
                invoice_number="INV-STAR",
                customer_id="cust_star",
                date=date(2026, 5, 10),
                amount=50000,
                due_date=date(2026, 5, 20),
                status="paid",
            ),
            Invoice(
                id="inv_risk",
                invoice_number="INV-RISK",
                customer_id="cust_risk",
                date=date(2026, 5, 1),
                amount=15000,
                due_date=date(2026, 5, 5),
                status="overdue",
            ),
        ],
        payments=[
            Payment(id="pay_star", customer_id="cust_star", amount=50000, date=date(2026, 5, 19), mode="upi", status="reconciled"),
        ],
    )

    segmentation = build_retailer_segmentation(repository=repo, as_of=date(2026, 5, 21), lookback_days=90)

    assert segmentation["mode"] == "local_contract_mock"
    assert segmentation["summary"] == {
        "customers": 3,
        "priority_retailers": 1,
        "credit_risk_retailers": 1,
        "dormant_retailers": 1,
        "total_revenue": 65000.0,
        "total_overdue": 15000.0,
    }
    assert segmentation["segments"][0] == {
        "customer_id": "cust_risk",
        "customer_name": "Risk Retail",
        "segment": "credit_risk",
        "revenue_last_90_days": 15000.0,
        "paid_amount_last_90_days": 0.0,
        "outstanding_amount": 15000.0,
        "overdue_amount": 15000.0,
        "days_since_last_invoice": 20,
        "credit_utilization_percent": 125.0,
        "recommended_action": "Owner review before fresh dispatch; recover overdue or approve credit exception.",
    }
    assert segmentation["segments"][1]["segment"] == "priority_retailer"
    assert segmentation["segments"][2]["segment"] == "dormant_or_untraded"
    assert segmentation["audit"] == {
        "external_crm_enrichment_called": False,
        "predictive_ml_model_called": False,
        "limitation": "Local retailer segmentation only; no predictive ML model or CRM enrichment integration was called.",
    }


def test_should_return_empty_retailer_segments_without_customers() -> None:
    segmentation = build_retailer_segmentation(repository=InMemoryRepository(), as_of=date(2026, 5, 21))

    assert segmentation["summary"]["customers"] == 0
    assert segmentation["segments"] == []
