from __future__ import annotations

from datetime import datetime

from apps.ares.ares.connectors.message_ingest import (
    WHATSAPP_SANDBOX_INGEST_LIMITATION,
    ingest_whatsapp_sandbox_payload,
)
from apps.ares.ares.orchestrator.intent_classifier import EventIntent, classify_event
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.workflows.whatsapp_business import record_whatsapp_delivery_receipt
from tests.ares.support import (
    assert_local_contract_audit,
    assert_redaction_safe_payload,
    whatsapp_inbound_message_payload,
    whatsapp_status_webhook_payload,
)


def test_should_normalize_whatsapp_sandbox_inbound_message_into_order_event() -> None:
    payload = whatsapp_inbound_message_payload()

    result = ingest_whatsapp_sandbox_payload(
        client_id="demo",
        payload=payload,
        received_at=datetime(2026, 5, 23, 9, 30),
    )

    assert result["mode"] == "local_contract_mock"
    assert result["status"] == "parsed"
    assert len(result["messages"]) == 1
    assert result["delivery_updates"] == []
    event = result["messages"][0]
    assert event.source == "whatsapp_sandbox"
    assert event.file_id == "wamid.sandbox.inbound.0001"
    assert event.sender == "919876543210"
    assert event.raw_text == "Raj Traders 20 carton Surf kal bhejna"
    assert event.metadata["provider"] == "whatsapp_business"
    assert event.metadata["sandbox"] is True
    assert event.metadata["profile_name"] == "Raj Traders Sandbox"
    assert event.metadata["phone_number_id"] == "meta_sandbox_phone_001"
    assert classify_event(event) == EventIntent.new_order
    assert_local_contract_audit(
        result["audit"],
        limitation=WHATSAPP_SANDBOX_INGEST_LIMITATION,
        provider="whatsapp_business",
        sandbox_payload_processed=True,
        webhook_signature_verified=False,
        live_api_called=False,
        production_message_processed=False,
    )


def test_should_normalize_whatsapp_sandbox_status_payload_and_feed_delivery_audit_sink() -> None:
    payload = whatsapp_status_webhook_payload()
    repo = InMemoryRepository()

    result = ingest_whatsapp_sandbox_payload(client_id="demo", payload=payload)

    assert result["status"] == "parsed"
    assert result["messages"] == []
    assert len(result["delivery_updates"]) == 1
    update = result["delivery_updates"][0]
    assert update["provider_message_id"] == "wamid.sandbox.msg.0001"
    assert update["recipient_phone"] == "919000000001"
    assert update["status"] == "delivered"
    assert update["conversation_id"] == "conv_sandbox_001"
    assert update["pricing_category"] == "utility"

    receipt = record_whatsapp_delivery_receipt(
        repository=repo,
        client_id="demo",
        approval_id=None,
        provider_message_id=update["provider_message_id"],
        recipient_phone=update["recipient_phone"],
        status=update["status"],
    )

    assert receipt["delivery_status"] == "delivered"
    assert receipt["message_drop"] is False
    assert repo.list_action_logs()[-1].action_type == "whatsapp_delivery_receipt"
    assert repo.list_action_logs()[-1].status == "executed"


def test_whatsapp_sandbox_payload_fixtures_are_redaction_safe() -> None:
    assert_redaction_safe_payload(whatsapp_inbound_message_payload())
    assert_redaction_safe_payload(whatsapp_status_webhook_payload())
