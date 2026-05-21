from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, Payment, PostDatedCheque
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.collections_dashboard import build_collections_dashboard


def test_should_build_collections_dashboard_from_overdues_pdc_reminders_and_credit_scores() -> None:
    repo = InMemoryRepository.from_records(
        customers=[
            Customer(id="cust_risk", name="Risk Retail", credit_limit=10000),
            Customer(id="cust_watch", name="Watch Retail", credit_limit=50000),
        ],
        invoices=[
            Invoice(id="inv_risk_old", invoice_number="INV-RISK-OLD", customer_id="cust_risk", amount=7000, due_date=date(2026, 4, 1), status="overdue"),
            Invoice(id="inv_risk_open", invoice_number="INV-RISK-OPEN", customer_id="cust_risk", amount=8000, due_date=date(2026, 5, 30), status="open"),
            Invoice(id="inv_watch_old", invoice_number="INV-WATCH-OLD", customer_id="cust_watch", amount=2000, due_date=date(2026, 5, 10), status="overdue"),
        ],
        payments=[
            Payment(id="pay_watch", customer_id="cust_watch", amount=1000, date=date(2026, 5, 20), mode="upi", status="reconciled"),
        ],
    )
    repo.upsert_post_dated_cheque(
        PostDatedCheque(
            id="pdc_bounced",
            party_id="cust_risk",
            amount=5000,
            cheque_date=date(2026, 5, 10),
            bank_name="HDFC Bank",
            cheque_number="111111",
            status="bounced",
        )
    )
    repo.upsert_post_dated_cheque(
        PostDatedCheque(
            id="pdc_due",
            party_id="cust_watch",
            amount=2000,
            cheque_date=date(2026, 5, 21),
            bank_name="ICICI Bank",
            cheque_number="222222",
            status="scheduled",
        )
    )
    approvals = ApprovalService(repo)
    approvals.create_approval_request(
        client_id="demo",
        action_type="send_customer_message",
        proposed_action="Send payment reminder",
        data={"customer": "cust_risk", "invoice_id": "inv_risk_old", "draft": "Please pay"},
        reason="test",
        source="payment_radar",
        confidence=0.9,
        dedupe_key="reminder:inv_risk_old",
    )

    dashboard = build_collections_dashboard(repository=repo, as_of=date(2026, 5, 21), lookback_days=90)

    assert dashboard["mode"] == "local_contract_mock"
    assert dashboard["summary"] == {
        "parties_with_dues": 2,
        "total_outstanding": 17000.0,
        "overdue_outstanding": 9000.0,
        "high_risk_parties": 1,
        "pending_reminders": 1,
        "pdc_actions": 2,
    }
    assert dashboard["priority_queue"][0] == {
        "customer_id": "cust_risk",
        "customer_name": "Risk Retail",
        "current_exposure": 15000.0,
        "overdue_amount": 7000.0,
        "oldest_overdue_days": 50,
        "credit_score": 15,
        "risk_band": "high",
        "pdc_risk_count": 1,
        "pending_reminder_count": 1,
        "collection_priority": "urgent",
        "recommended_action": "Block fresh dispatch unless owner approves recovery or credit exception.",
    }
    assert dashboard["pdc_actions"] == [
        {"pdc_id": "pdc_bounced", "party_id": "cust_risk", "amount": 5000.0, "cheque_date": "2026-05-10", "status": "bounced", "code": "pdc_bounced"},
        {"pdc_id": "pdc_due", "party_id": "cust_watch", "amount": 2000.0, "cheque_date": "2026-05-21", "status": "scheduled", "code": "pdc_due"},
    ]
    assert dashboard["pending_reminders"] == [
        {"approval_id": repo.list_pending_approvals()[0].id, "customer_id": "cust_risk", "invoice_id": "inv_risk_old"}
    ]
    assert dashboard["audit"] == {
        "external_crm_called": False,
        "whatsapp_automation_performed": False,
        "external_bank_feed_called": False,
        "limitation": "Local collections dashboard only; no live CRM, WhatsApp automation, or bank integration was called.",
    }


def test_should_return_empty_collections_dashboard_without_dues() -> None:
    dashboard = build_collections_dashboard(repository=InMemoryRepository(), as_of=date(2026, 5, 21))

    assert dashboard["summary"]["parties_with_dues"] == 0
    assert dashboard["priority_queue"] == []
