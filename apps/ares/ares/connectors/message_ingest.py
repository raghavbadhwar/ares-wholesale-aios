"""Forwarded WhatsApp/Telegram text ingestion."""

from __future__ import annotations

from datetime import datetime

from apps.ares.ares.connectors.events import new_event
from apps.ares.ares.data.models import IngestedEvent

WHATSAPP_SANDBOX_INGEST_LIMITATION = (
    "Local WhatsApp sandbox ingest only; no live Meta webhook registration, "
    "message fetch, or production WhatsApp processing was performed."
)


def ingest_forwarded_message(
    *,
    client_id: str,
    sender: str,
    message_text: str,
    timestamp: datetime | None = None,
    chat_hint: str | None = None,
) -> IngestedEvent:
    metadata = {"chat_hint": chat_hint} if chat_hint else {}
    return new_event(
        source="message_forward",
        client_id=client_id,
        raw_text=message_text.strip(),
        timestamp=timestamp,
        sender=sender,
        metadata=metadata,
        confidence=0.95,
    )


def ingest_whatsapp_sandbox_payload(
    *,
    client_id: str,
    payload: dict,
    received_at: datetime | None = None,
) -> dict:
    messages: list[IngestedEvent] = []
    delivery_updates: list[dict] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            metadata = value.get("metadata", {}) or {}
            phone_number_id = metadata.get("phone_number_id")
            for message in value.get("messages", []) or []:
                text = (message.get("text") or {}).get("body", "")
                contact = (value.get("contacts") or [{}])[0] if value.get("contacts") else {}
                profile = contact.get("profile", {}) or {}
                messages.append(
                    new_event(
                        source="whatsapp_sandbox",
                        client_id=client_id,
                        raw_text=text,
                        timestamp=received_at,
                        sender=message.get("from"),
                        file_id=message.get("id"),
                        metadata={
                            "provider": "whatsapp_business",
                            "sandbox": True,
                            "profile_name": profile.get("name"),
                            "phone_number_id": phone_number_id,
                        },
                        confidence=0.95,
                    )
                )
            for status in value.get("statuses", []) or []:
                conversation = status.get("conversation", {}) or {}
                pricing = status.get("pricing", {}) or {}
                delivery_updates.append(
                    {
                        "provider_message_id": status.get("id"),
                        "recipient_phone": status.get("recipient_id"),
                        "status": status.get("status"),
                        "conversation_id": conversation.get("id"),
                        "pricing_category": pricing.get("category"),
                    }
                )
    return {
        "mode": "local_contract_mock",
        "status": "parsed",
        "messages": messages,
        "delivery_updates": delivery_updates,
        "delivery_receipts": [],
        "audit": {
            "provider": "whatsapp_business",
            "sandbox_payload_processed": True,
            "webhook_signature_verified": False,
            "live_api_called": False,
            "production_message_processed": False,
            "limitation": WHATSAPP_SANDBOX_INGEST_LIMITATION,
        },
    }
