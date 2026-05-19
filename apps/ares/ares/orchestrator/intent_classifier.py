"""Deterministic intent classifier with Hinglish-friendly keywords."""

from __future__ import annotations

from enum import StrEnum

from apps.ares.ares.data.models import IngestedEvent


class EventIntent(StrEnum):
    new_order = "new_order"
    payment_update = "payment_update"
    payment_promise = "payment_promise"
    complaint = "complaint"
    stock_update = "stock_update"
    supplier_update = "supplier_update"
    invoice_document = "invoice_document"
    export_file = "export_file"
    unclear = "unclear"


KEYWORDS: dict[EventIntent, tuple[str, ...]] = {
    EventIntent.new_order: ("bhej", "send", "order", "carton", "box", "pcs", "maal", "deliver"),
    EventIntent.payment_update: ("paid", "payment done", "utr", "neft", "imps", "received", "jama"),
    EventIntent.payment_promise: ("kal payment", "promise", "pay tomorrow", "shaam tak", "monday payment"),
    EventIntent.complaint: ("complaint", "damage", "broken", "wrong item", "late", "return"),
    EventIntent.stock_update: ("stock", "low", "khatam", "available", "balance stock"),
    EventIntent.supplier_update: ("supplier", "purchase", "po", "rate", "dispatch from"),
    EventIntent.invoice_document: ("invoice", "bill", "gst", "tax invoice"),
    EventIntent.export_file: ("tally", "busy", "vyapar", "marg", ".csv", ".xlsx"),
}


def classify_text(text: str) -> EventIntent:
    normalized = text.lower()
    for intent, keywords in KEYWORDS.items():
        if any(keyword in normalized for keyword in keywords):
            return intent
    return EventIntent.unclear


def classify_event(event: IngestedEvent) -> EventIntent:
    if event.file_path or event.file_id:
        text = f"{event.raw_text} {event.file_path or ''}".lower()
        if any(ext in text for ext in (".csv", ".xlsx")):
            return EventIntent.export_file
        if any(ext in text for ext in (".pdf", ".jpg", ".jpeg", ".png")):
            return EventIntent.invoice_document
    return classify_text(event.raw_text)

