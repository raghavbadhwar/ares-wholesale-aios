"""Rules for deciding what becomes durable business memory."""

from __future__ import annotations

from dataclasses import dataclass


SAVE_WORTHY_CATEGORIES = {
    "customer_payment_pattern",
    "customer_reorder_pattern",
    "supplier_reliability",
    "supplier_lead_time",
    "staff_responsibility",
    "owner_preference",
    "business_rule",
    "sku_seasonality",
    "repeated_issue",
    "pdc_bounce_pattern",
}

NOISE_CATEGORIES = {
    "one_time_order",
    "temporary_payment_status",
    "raw_chat_dump",
    "invoice_status",
    "one_off_message",
}

SENSITIVE_CATEGORIES = {"business_rule", "owner_preference", "staff_responsibility"}


@dataclass(frozen=True)
class MemoryCandidate:
    category: str
    subject_id: str | None
    content: str
    observations: int = 1
    confidence: float = 1.0
    source: str = ""


@dataclass(frozen=True)
class MemoryDecision:
    save: bool
    reason: str
    requires_approval: bool = False


def evaluate_memory_candidate(candidate: MemoryCandidate) -> MemoryDecision:
    if candidate.category in NOISE_CATEGORIES:
        return MemoryDecision(False, "transient or noisy fact")
    if candidate.category not in SAVE_WORTHY_CATEGORIES:
        return MemoryDecision(False, "category is not configured as durable memory")
    if candidate.observations < 2 and candidate.category not in {"business_rule", "owner_preference"}:
        return MemoryDecision(False, "pattern needs repeated observations")
    if candidate.confidence < 0.7:
        return MemoryDecision(False, "confidence below durable memory threshold")
    return MemoryDecision(
        True,
        "durable business pattern",
        requires_approval=candidate.category in SENSITIVE_CATEGORIES,
    )

