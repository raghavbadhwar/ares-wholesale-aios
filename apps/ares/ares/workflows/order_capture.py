"""Capture wholesale orders from forwarded Hinglish/Hindi/English messages."""

from __future__ import annotations

from datetime import date
import re
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Customer, IngestedEvent, Order, OrderExtractionResult, OrderItem, ProductSKU, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

ITEM_RE = re.compile(
    r"(?P<qty>\d+(?:\.\d+)?)\s*"
    r"(?P<unit>carton|ctn|box|dabba|pcs|pc|piece|pieces|kg|kilo|bag|bags|packet|pkt|peti)?\s+"
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9 _/-]{1,48}?)"
    r"(?=\s+(?:aur\s+)?\d+(?:\.\d+)?\s*(?:carton|ctn|box|dabba|pcs|pc|piece|pieces|kg|kilo|bag|bags|packet|pkt|peti)?\b|\s+(?:kal|aaj|bhejna|bhej|dena|please|pls|urgent)\b|$)",
    re.IGNORECASE,
)
NOISE_WORDS = {"kal", "aaj", "bhejna", "bhej", "dena", "please", "pls", "urgent", "chahiye", "chaahiye"}
DEFAULT_CREDIT_HARD_STOP_DAYS = 45
DEFAULT_UNKNOWN_ITEM_VALUE = 1000.0


def _clean_name(value: str) -> str:
    parts = [part for part in value.strip(" -_/.,").split() if part.lower() not in NOISE_WORDS]
    return " ".join(parts).strip() or value.strip()


def _normalized_unit(value: str | None) -> str:
    unit = (value or "unit").lower()
    return {"ctn": "carton", "pc": "pcs", "piece": "pcs", "pieces": "pcs", "kilo": "kg", "pkt": "packet", "dabba": "box", "peti": "box"}.get(unit, unit)


def _find_customer(repository: BusinessRepository, customer_hint: str | None) -> Customer | None:
    if not customer_hint:
        return None
    normalized = customer_hint.strip().lower()
    for customer in repository.get_customers():
        names = [customer.id, customer.name, *customer.aliases]
        if any(name.strip().lower() == normalized for name in names if name):
            return customer
    return None


def _find_product(repository: BusinessRepository, item_name: str) -> ProductSKU | None:
    normalized = item_name.strip().lower()
    for product in repository.get_products():
        names = [product.id, product.name, *product.aliases]
        if any(name.strip().lower() == normalized for name in names if name):
            return product
    return None


def _estimate_order_value(order: Order, repository: BusinessRepository) -> float:
    total = 0.0
    for item in order.items:
        product = _find_product(repository, item.name)
        unit_price = product.selling_price if product and product.selling_price is not None else DEFAULT_UNKNOWN_ITEM_VALUE
        total += item.quantity * unit_price
    return total


def _customer_open_exposure(repository: BusinessRepository, customer_id: str) -> float:
    return sum(invoice.amount for invoice in repository.get_outstanding() if invoice.customer_id == customer_id)


def _oldest_overdue_days(repository: BusinessRepository, customer_id: str, *, today: date | None = None) -> int:
    current_day = today or date.today()
    overdue_days = [max((current_day - invoice.due_date).days, 0) for invoice in repository.get_outstanding() if invoice.customer_id == customer_id and invoice.due_date and invoice.status == "overdue"]
    return max(overdue_days, default=0)


def _apply_credit_guardrails(
    order: Order,
    *,
    event: IngestedEvent,
    repository: BusinessRepository,
    approvals: ApprovalService,
) -> None:
    customer = _find_customer(repository, order.customer_id)
    if customer is None:
        return

    oldest_overdue_days = _oldest_overdue_days(repository, customer.id)
    if oldest_overdue_days > DEFAULT_CREDIT_HARD_STOP_DAYS:
        approvals.create_approval_request(
            client_id=event.client_id,
            action_type="block_dispatch",
            proposed_action="Block dispatch until overdue exposure is cleared or owner overrides.",
            data={
                "order_id": order.id,
                "customer": customer.id,
                "oldest_overdue_days": oldest_overdue_days,
            },
            reason="Customer has crossed the hard-stop overdue threshold.",
            source=event.source,
            confidence=0.97,
            risk_level=RiskLevel.high,
            dedupe_key=f"block_dispatch:{customer.id}:{order.id}",
        )
        return

    if customer.credit_limit is None:
        return

    current_exposure = _customer_open_exposure(repository, customer.id)
    projected_exposure = current_exposure + _estimate_order_value(order, repository)
    if projected_exposure <= customer.credit_limit:
        return

    approvals.create_approval_request(
        client_id=event.client_id,
        action_type="approve_credit_extension",
        proposed_action="Review and approve credit extension before dispatching this order.",
        data={
            "order_id": order.id,
            "customer": customer.id,
            "credit_limit": customer.credit_limit,
            "current_exposure": current_exposure,
            "projected_exposure": projected_exposure,
        },
        reason="Projected exposure exceeds the customer's configured credit limit.",
        source=event.source,
        confidence=0.9,
        risk_level=RiskLevel.high,
        dedupe_key=f"credit_extension:{customer.id}:{order.id}",
    )


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
    _apply_credit_guardrails(order, event=event, repository=repository, approvals=approvals)
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
