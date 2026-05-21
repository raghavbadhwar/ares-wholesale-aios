from __future__ import annotations

from apps.ares.ares.approvals.service import ApprovalService, requires_approval
from apps.ares.ares.data.models import Customer
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.execution.actions import ActionExecutor, InMemoryMessageSender
from apps.ares.ares.workflows.whatsapp_business import (
    prepare_whatsapp_business_message,
    record_whatsapp_delivery_receipt,
)


def test_should_prepare_approval_gated_whatsapp_business_message_contract() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Ramesh Stores", phone="+919999999999", preferred_language="marathi")]
    )
    approvals = ApprovalService(repo)

    draft = prepare_whatsapp_business_message(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        template_name="payment_reminder",
        body="नमस्कार, तुमची उधारी रक्कम बाकी आहे.",
        requested_by="owner",
        dedupe_key="waba:payment:inv_1",
    )

    assert requires_approval("send_whatsapp_business_message")
    assert draft["mode"] == "contract_only_mock"
    assert draft["status"] == "approval_required"
    assert draft["selected_language"] == "marathi"
    assert draft["audit"] == {
        "requested_by": "owner",
        "approval_required": True,
        "external_whatsapp_business_api_called": False,
        "limitation": "Contract-only WhatsApp Business surface; no Meta/WhatsApp production API, webhook, or template registry was called.",
    }
    pending = repo.list_pending_approvals()[0]
    assert pending.type == "send_whatsapp_business_message"
    assert pending.data["channel"] == "whatsapp_business"
    assert pending.data["template_name"] == "payment_reminder"
    assert pending.data["recipient_phone"] == "+919999999999"
    assert pending.data["idempotency_key"] == "waba:payment:inv_1"


def test_should_execute_approved_whatsapp_contract_and_record_delivery_receipt() -> None:
    repo = InMemoryRepository.from_records(
        customers=[Customer(id="cust_1", name="Ramesh Stores", phone="+919999999999")]
    )
    approvals = ApprovalService(repo)
    draft = prepare_whatsapp_business_message(
        repository=repo,
        approvals=approvals,
        client_id="demo",
        customer_id="cust_1",
        template_name="order_confirmation",
        body="Order confirmed",
        requested_by="owner",
    )
    approvals.approve_request(draft["approval_id"], decided_by="owner")
    sender = InMemoryMessageSender()

    execution = ActionExecutor(repo, message_sender=sender).execute_approved(draft["approval_id"])
    receipt = record_whatsapp_delivery_receipt(
        repository=repo,
        client_id="demo",
        approval_id=draft["approval_id"],
        provider_message_id="mock_waba_msg_1",
        recipient_phone="+919999999999",
        status="delivered",
    )

    assert execution.status == "executed"
    assert sender.sent_messages == [{"recipient": "+919999999999", "body": "Order confirmed"}]
    assert execution.result["channel"] == "whatsapp_business"
    assert execution.result["template_name"] == "order_confirmation"
    assert execution.result["external_whatsapp_business_api_called"] is False
    assert receipt["message_drop"] is False
    assert repo.list_action_logs()[-1].action_type == "whatsapp_delivery_receipt"
