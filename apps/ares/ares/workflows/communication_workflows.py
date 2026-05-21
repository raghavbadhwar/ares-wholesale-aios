"""Local automated communication workflow drafts."""

from __future__ import annotations

from datetime import date
from typing import Any

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, Invoice, Order, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

LOCAL_COMMUNICATION_WORKFLOW_LIMITATION = (
    "Local automated communication workflow only; no live WhatsApp automation or CRM campaign execution was performed."
)


def _customers(repository: BusinessRepository) -> dict[str, Customer]:
    return {customer.id: customer for customer in repository.get_customers()}


def _payment_reminder_draft(customer: Customer, invoice: Invoice, as_of: date) -> str:
    days = (as_of - invoice.due_date).days if invoice.due_date else 0
    return f"Namaste {customer.name} ji, invoice {invoice.invoice_number} ka payment {days} din overdue hai. Kripya payment status confirm karein."


def _order_confirmation_draft(customer: Customer, order: Order) -> str:
    item_word = "item" if len(order.items) == 1 else "items"
    return f"Namaste {customer.name} ji, order {order.id} mein {len(order.items)} {item_word} receive hua hai. Dispatch se pehle confirm kar rahe hain."


def _create_message_approval(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    customer: Customer,
    workflow_type: str,
    draft: str,
    record_id: str,
) -> str:
    approval = approvals.create_approval_request(
        client_id=client_id,
        action_type="send_customer_message",
        proposed_action=f"Send {workflow_type.replace('_', ' ')} to {customer.name}",
        data={
            "customer_id": customer.id,
            "recipient": customer.phone,
            "draft": draft,
            "workflow_type": workflow_type,
            "record_id": record_id,
        },
        reason="Automated customer communication must be owner-approved before sending.",
        source="communication_workflows",
        confidence=0.88,
        risk_level=RiskLevel.medium,
        dedupe_key=f"communication:{workflow_type}:{customer.id}:{record_id}",
    )
    return approval.id


def _payment_reminder_drafts(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    as_of: date,
) -> tuple[list[dict[str, Any]], int]:
    customers = _customers(repository)
    drafts: list[dict[str, Any]] = []
    skipped = 0
    for invoice in repository.get_invoices():
        if invoice.status.strip().lower() != "overdue":
            continue
        customer = customers.get(invoice.customer_id or "")
        if customer is None or not customer.phone:
            skipped += 1
            continue
        draft = _payment_reminder_draft(customer, invoice, as_of)
        approval_id = _create_message_approval(
            repository=repository,
            approvals=approvals,
            client_id=client_id,
            customer=customer,
            workflow_type="payment_reminder",
            draft=draft,
            record_id=invoice.id,
        )
        drafts.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "workflow_type": "payment_reminder",
                "recipient": customer.phone,
                "draft": draft,
                "approval_id": approval_id,
            }
        )
    return drafts, skipped


def _order_confirmation_drafts(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
) -> tuple[list[dict[str, Any]], int]:
    customers = _customers(repository)
    drafts: list[dict[str, Any]] = []
    skipped = 0
    for order in repository.list_orders(status="pending"):
        customer = customers.get(order.customer_id or "")
        if customer is None or not customer.phone:
            skipped += 1
            continue
        draft = _order_confirmation_draft(customer, order)
        approval_id = _create_message_approval(
            repository=repository,
            approvals=approvals,
            client_id=client_id,
            customer=customer,
            workflow_type="order_confirmation",
            draft=draft,
            record_id=order.id,
        )
        drafts.append(
            {
                "customer_id": customer.id,
                "customer_name": customer.name,
                "workflow_type": "order_confirmation",
                "recipient": customer.phone,
                "draft": draft,
                "approval_id": approval_id,
            }
        )
    return drafts, skipped


def prepare_automated_communication_workflow(
    *,
    repository: BusinessRepository,
    approvals: ApprovalService,
    client_id: str,
    workflow_type: str,
    as_of: date,
    requested_by: str,
) -> dict[str, Any]:
    """Draft local automated communications and gate every send behind approval."""
    if workflow_type == "payment_reminder":
        drafts, skipped = _payment_reminder_drafts(repository=repository, approvals=approvals, client_id=client_id, as_of=as_of)
    elif workflow_type == "order_confirmation":
        drafts, skipped = _order_confirmation_drafts(repository=repository, approvals=approvals, client_id=client_id)
    else:
        raise ValueError(f"Unsupported communication workflow: {workflow_type}")

    summary = {"drafts": len(drafts), "approvals_created": len(drafts), "skipped": skipped}
    return {
        "mode": "local_contract_mock",
        "status": "approval_required" if drafts else "no_messages_to_draft",
        "workflow_type": workflow_type,
        "as_of": as_of.isoformat(),
        "summary": summary,
        "drafts": drafts,
        "audit": {
            "requested_by": requested_by,
            "approval_required": bool(drafts),
            "whatsapp_automation_performed": False,
            "crm_campaign_called": False,
            "limitation": LOCAL_COMMUNICATION_WORKFLOW_LIMITATION,
        },
    }
