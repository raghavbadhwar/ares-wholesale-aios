"""Forwarded WhatsApp/Telegram text ingestion."""

from __future__ import annotations

from datetime import datetime

from apps.ares.ares.connectors.events import new_event
from apps.ares.ares.data.models import IngestedEvent
from apps.ares.ares.workflows.regional_language import detect_language


def ingest_forwarded_message(
    *,
    client_id: str,
    sender: str,
    message_text: str,
    timestamp: datetime | None = None,
    chat_hint: str | None = None,
) -> IngestedEvent:
    detection = detect_language(message_text)
    metadata = {
        "detected_language": detection["language"],
        "language_confidence": detection["confidence"],
        "language_detection_method": detection["method"],
    }
    if chat_hint:
        metadata["chat_hint"] = chat_hint
    return new_event(
        source="message_forward",
        client_id=client_id,
        raw_text=message_text.strip(),
        timestamp=timestamp,
        sender=sender,
        metadata=metadata,
        confidence=0.95,
    )
