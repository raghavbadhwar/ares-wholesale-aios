"""Capture wholesale orders from forwarded Hinglish/Hindi/English messages."""

from __future__ import annotations

import re
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import IngestedEvent, Order, OrderExtractionResult, OrderItem, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

ITEM_RE = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>carton|ctn|box|dabba|pcs|pc|piece|pieces|kg|kilo|bag|bags|packet|pkt|peti)?\s+"
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9 _/-]{1,48}?)"
    r"(?=\s+(?:aur\s+)?\d+(?:\.\d+)?\s*(?:carton|ctn|box|dabba|pcs|pc|piece|pieces|kg|kilo|bag|bags|packet|pkt|peti)?\b|\s+(?:kal|aaj|bhejna|bhej|dena|please|pls|urgent)\b|$)",
    re.IGNORECASE,
)
NOISE_WORDS = {"kal", "aaj", "bhejna", "bhej", "dena", "please", "pls", "urgent", "chahiye", "chaahiye"}


def _clean_name(value: str) -> str:
    parts = [part for part in value.strip(" -_/.,").split() if part.lower() not in NOISE_WORDS]
    return " ".join(parts).strip() or value.strip()


def _normalized_unit(value: str | None) -> str:
    unit = (value or "unit").lower()
    return {"ctn": "carton", "pc": "pcs", "piece": "pcs", "pieces": "pcs", "kilo": "kg", "pkt": "packet", "dabba": "box", "peti": "box"}.get(unit, unit)


def extract_order_result(event: IngestedEvent) -> OrderExtractionResult:
    items: list[OrderItem] = []
    for match in ITEM_RE.finditer(event.raw_text):
        name = _clean_name(match.group("name"))
        if not name or name.lower() in NOISE_WORDS:
            continue
        items.append(
            OrderItem(
                name=name,
                quantity=float(match.group("qty")),
                unit=_normalized_unit(match.group("unit")),
            )
        )

    missing_fields: list[str] = []
    warnings: list[str] = []
    if not items:
        missing_fields.append("items")
        warnings.append("No item quantity/product pair could be extracted from the message.")
    customer_hint = event.metadata.get("chat_hint") or event.sender
    if not customer_hint:
        missing_fields.append("customer")

    confidence = 0.9 if items and customer_hint else 0.55 if items else 0.35
    order = Order(
        id=f"ord_{uuid4().hex[:12]}",
        customer_id=customer_hint,
        source=event.source,
        raw_text=event.raw_text,
        file_id=event.file_id,
        items=items,
        confidence=confidence,
    )
    return OrderExtractionResult(
        order=order,
        missing_fields=missing_fields,
        warnings=warnings,
        needs_approval=confidence < 0.75 or bool(missing_fields),
    )


def extract_order(event: IngestedEvent) -> Order:
    return extract_order_result(event).order


def capture_order(event: IngestedEvent, repository: BusinessRepository, approvals: ApprovalService) -> Order:
    result = extract_order_result(event)
    order = repository.create_order(result.order)
    if result.needs_approval:
        approvals.create_approval_request(
            client_id=event.client_id,
            action_type="confirm_unclear_order",
            proposed_action="Confirm unclear order before adding to dispatch queue",
            data={
                "order_id": order.id,
                "raw_text": event.raw_text,
                "customer": order.customer_id,
                "missing_fields": result.missing_fields,
                "warnings": result.warnings,
            },
            reason="Order extraction is incomplete or low confidence.",
            source=event.source,
            confidence=order.confidence,
            risk_level=RiskLevel.medium,
            dedupe_key=f"unclear_order:{event.id}",
        )
    return order
