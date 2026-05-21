"""Local Account Aggregator consent and data contracts."""

from __future__ import annotations

from datetime import date
from statistics import mean
from typing import Any
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import ActionExecutionLog, Customer, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

ACCOUNT_AGGREGATOR_LIMITATION = (
    "Local Account Aggregator contract only; no RBI AA network, consent submission, bank data pull, "
    "lender integration, or credit-limit change was performed."
)


def prepare_account_aggregator_consent_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    customer_id: str,
    requested_by: str,
    consent_purpose: str,
    data_range_days: int,
) -> dict[str, Any]:
    """Prepare an owner-approved AA consent contract for a customer."""
    customer = _find_customer(repository, customer_id)
    request = {
        "consent_request_id": f"aa_consent_{uuid4().hex[:12]}",
        "customer_id": customer.id,
        "customer_name": customer.name,
        "purpose": consent_purpose,
        "data_range_days": data_range_days,
        "data_scopes": ["deposit_account_transactions", "account_balance", "returned_items"],
        "consent_channel": "local_contract_review",
    }
    audit = _audit(requested_by=requested_by, approval_required=True)
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="request_account_aggregator_consent",
        proposed_action=f"Review AA consent request for {customer.name}",
        data={"request": request, "mode": "local_contract_mock"},
        reason="Account Aggregator consent and financial data use must be reviewed before any external consent flow.",
        source="account_aggregator",
        confidence=0.82,
        risk_level=RiskLevel.high,
        dedupe_key=f"aa_consent:{client_id}:{customer.id}:{request['consent_request_id']}",
    )
    return {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "request": request,
        "audit": audit,
    }


def ingest_account_aggregator_financial_data_contract(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    customer_id: str,
    consent_id: str,
    requested_by: str,
    as_of: date,
    financial_summary: dict[str, Any],
) -> dict[str, Any]:
    """Convert a local AA-shaped financial summary into an approval-gated credit signal."""
    customer = _find_customer(repository, customer_id)
    credit_signal = _credit_signal(customer=customer, financial_summary=financial_summary)
    audit = _audit(requested_by=requested_by, approval_required=True)
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="review_account_aggregator_credit_signal",
        proposed_action=f"Review AA credit signal for {customer.name}",
        data={
            "customer_id": customer.id,
            "consent_id": consent_id,
            "as_of": as_of.isoformat(),
            "credit_signal": credit_signal,
            "mode": "local_contract_mock",
        },
        reason="AA-derived credit recommendations can change customer exposure and require owner approval.",
        source="account_aggregator",
        confidence=0.78,
        risk_level=RiskLevel.high,
        dedupe_key=f"aa_credit_signal:{client_id}:{customer.id}:{consent_id}",
    )
    result = {
        "mode": "local_contract_mock",
        "status": "approval_required",
        "approval_id": approval.id,
        "consent_id": consent_id,
        "as_of": as_of.isoformat(),
        "credit_signal": credit_signal,
        "audit": audit,
    }
    repository.save_action_log(
        ActionExecutionLog(
            id=f"act_{uuid4().hex[:12]}",
            client_id=client_id,
            approval_id=approval.id,
            action_type="account_aggregator_financial_data_contract",
            status=result["status"],
            result={
                "customer_id": customer.id,
                "consent_id": consent_id,
                "recommendation": credit_signal["recommendation"],
                "aa_network_called": audit["aa_network_called"],
                "bank_data_pulled": audit["bank_data_pulled"],
                "credit_limit_changed": audit["credit_limit_changed"],
                "limitation": audit["limitation"],
            },
        )
    )
    return result


def _find_customer(repository: BusinessRepository, customer_id: str) -> Customer:
    for customer in repository.get_customers():
        if customer.id == customer_id:
            return customer
    raise KeyError(f"Customer not found: {customer_id}")


def _credit_signal(*, customer: Customer, financial_summary: dict[str, Any]) -> dict[str, Any]:
    inflows = [float(value) for value in financial_summary.get("monthly_inflows", [])]
    average_monthly_inflow = round(mean(inflows), 2) if inflows else 0.0
    average_balance = round(float(financial_summary.get("average_balance", 0)), 2)
    returned_items = int(financial_summary.get("returned_items", 0))
    suggested_limit = round(min(average_monthly_inflow * 0.5, average_balance * 3), 2) if average_monthly_inflow else 0.0
    recommendation = "review_credit_limit_enhancement" if suggested_limit > float(customer.credit_limit or 0) and returned_items <= 1 else "manual_credit_review"
    return {
        "customer_id": customer.id,
        "average_monthly_inflow": average_monthly_inflow,
        "average_balance": average_balance,
        "returned_items": returned_items,
        "current_credit_limit": round(float(customer.credit_limit or 0), 2),
        "suggested_credit_limit": suggested_limit,
        "recommendation": recommendation,
    }


def _audit(*, requested_by: str, approval_required: bool) -> dict[str, Any]:
    return {
        "requested_by": requested_by,
        "approval_required": approval_required,
        "aa_network_called": False,
        "consent_submitted": False,
        "bank_data_pulled": False,
        "credit_limit_changed": False,
        "limitation": ACCOUNT_AGGREGATOR_LIMITATION,
    }
