"""Normalized event helpers for incoming Ares data."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from apps.ares.ares.data.models import IngestedEvent


def new_event(
    *,
    source: str,
    client_id: str,
    raw_text: str = "",
    file_path: str | None = None,
    file_id: str | None = None,
    timestamp: datetime | None = None,
    sender: str | None = None,
    metadata: dict | None = None,
    confidence: float = 1.0,
) -> IngestedEvent:
    return IngestedEvent(
        id=f"evt_{uuid4().hex[:12]}",
        source=source,
        client_id=client_id,
        raw_text=raw_text,
        file_path=file_path,
        file_id=file_id,
        timestamp=timestamp or datetime.now().astimezone(),
        sender=sender,
        metadata=metadata or {},
        confidence=confidence,
    )

