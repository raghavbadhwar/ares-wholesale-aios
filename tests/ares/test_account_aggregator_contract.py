from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.account_aggregator import (
    ACCOUNT_AGGREGATOR_LIMITATION,
    ingest_account_aggregator_financial_data_contract,
    prepare_account_aggregator_consent_contract,
)


def test_should_prepare_approval_gated_account_aggregator_consent_contract() -> None:
    repo = InMemoryRepository.from_records(customers=[Customer(id="cust_1", name="Raj Retail", phone="+919999999999")])
    approvals = ApprovalService(repo)

    consent = prepare_account_aggregator_consent_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        requested_by="owner",
        consent_purpose="credit_limit_review",
        data_range_days=180,
    )

    assert consent["mode"] == "local_contract_mock"
    assert consent["status"] == "approval_required"
    assert consent["request"]["customer_id"] == "cust_1"
    assert consent["request"]["purpose"] == "credit_limit_review"
    assert consent["request"]["data_scopes"] == ["deposit_account_transactions", "account_balance", "returned_items"]
    assert consent["audit"] == {
        "requested_by": "owner",
        "approval_required": True,
        "aa_network_called": False,
        "consent_submitted": False,
        "bank_data_pulled": False,
        "credit_limit_changed": False,
        "limitation": ACCOUNT_AGGREGATOR_LIMITATION,
    }
    assert repo.list_pending_approvals()[0].type == "request_account_aggregator_consent"


def test_should_prepare_credit_signal_from_local_aa_financial_summary_without_bank_pull() -> None:
    repo = InMemoryRepository.from_records(customers=[Customer(id="cust_1", name="Raj Retail", credit_limit=25000)])
    approvals = ApprovalService(repo)

    signal = ingest_account_aggregator_financial_data_contract(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        consent_id="consent_local_1",
        requested_by="owner",
        as_of=date(2026, 5, 21),
        financial_summary={
            "monthly_inflows": [100000, 120000, 90000],
            "average_balance": 30000,
            "returned_items": 1,
        },
    )

    assert signal["mode"] == "local_contract_mock"
    assert signal["status"] == "approval_required"
    assert signal["credit_signal"] == {
        "customer_id": "cust_1",
        "average_monthly_inflow": 103333.33,
        "average_balance": 30000.0,
        "returned_items": 1,
        "current_credit_limit": 25000.0,
        "suggested_credit_limit": 51666.67,
        "recommendation": "review_credit_limit_enhancement",
    }
    assert signal["audit"]["aa_network_called"] is False
    assert signal["audit"]["bank_data_pulled"] is False
    assert signal["audit"]["credit_limit_changed"] is False
    assert signal["audit"]["limitation"] == ACCOUNT_AGGREGATOR_LIMITATION
    assert repo.list_pending_approvals()[0].type == "review_account_aggregator_credit_signal"
    assert repo.list_action_logs()[0].action_type == "account_aggregator_financial_data_contract"
