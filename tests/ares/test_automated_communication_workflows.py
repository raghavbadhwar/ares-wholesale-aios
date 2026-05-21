from __future__ import annotations

from datetime import date

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, Order, OrderItem
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.communication_workflows import prepare_automated_communication_workflow


def test_should_draft_payment_reminder_communications_as_approval_gated_messages() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Raj Retail", phone="+919999999999", preferred_language="english_hinglish")],
        invoices=[
            Invoice(id="inv_1", invoice_number="INV-1", customer_id="cust_1", amount=5000, due_date=date(2026, 5, 1), status="overdue")
        ],
    )
    approvals = ApprovalService(repo)

    workflow = prepare_automated_communication_workflow(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        workflow_type="payment_reminder",
        as_of=date(2026, 5, 21),
        requested_by="owner",
    )

    assert workflow["mode"] == "local_contract_mock"
    assert workflow["status"] == "approval_required"
    assert workflow["summary"] == {"drafts": 1, "approvals_created": 1, "skipped": 0}
    assert workflow["drafts"] == [
        {
            "customer_id": "cust_1",
            "customer_name": "Raj Retail",
            "workflow_type": "payment_reminder",
            "recipient": "+919999999999",
            "draft": "Namaste Raj Retail ji, invoice INV-1 ka payment 20 din overdue hai. Kripya payment status confirm karein.",
            "approval_id": repo.list_pending_approvals()[0].id,
        }
    ]
    assert repo.list_pending_approvals()[0].type == "send_customer_message"
    assert workflow["audit"] == {
        "requested_by": "owner",
        "approval_required": True,
        "whatsapp_automation_performed": False,
        "crm_campaign_called": False,
        "limitation": "Local automated communication workflow only; no live WhatsApp automation or CRM campaign execution was performed.",
    }


def test_should_draft_order_confirmation_communications_without_sending() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Raj Retail", phone="+919999999999")],
        orders=[Order(id="ord_1", customer_id="cust_1", items=[OrderItem(name="Soap", quantity=2)], status="pending")],
    )

    workflow = prepare_automated_communication_workflow(
        repository=repo,
        approvals=ApprovalService(repo),
        client_id="demo",
        workflow_type="order_confirmation",
        as_of=date(2026, 5, 21),
        requested_by="owner",
    )

    assert workflow["summary"]["drafts"] == 1
    assert workflow["drafts"][0]["draft"] == "Namaste Raj Retail ji, order ord_1 mein 1 item receive hua hai. Dispatch se pehle confirm kar rahe hain."
    assert repo.list_pending_approvals()[0].data["draft"] == workflow["drafts"][0]["draft"]


def test_should_return_noop_when_communication_workflow_has_no_eligible_records() -> None:
    workflow = prepare_automated_communication_workflow(
        repository=InMemoryRepository(),
        approvals=ApprovalService(InMemoryRepository()),
        client_id="demo",
        workflow_type="payment_reminder",
        as_of=date(2026, 5, 21),
        requested_by="owner",
    )

    assert workflow["status"] == "no_messages_to_draft"
    assert workflow["drafts"] == []
