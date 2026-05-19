"""Payment extraction and low-confidence approval behavior."""

from __future__ import annotations

import re
from datetime import date
from uuid import uuid4

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.data.models import Payment, RiskLevel
from apps.ares.ares.data.repository import BusinessRepository

AMOUNT_RE = re.compile(r"(?:inr|rs\.?|amount)?\s*(?P<amount>\d{3,}(?:\.\d+)?)", re.IGNORECASE)
REF_RE = re.compile(r"\b(?:utr|ref|reference)[:\s-]*(?P<ref>[A-Za-z0-9-]{6,})", re.IGNORECASE)


def extract_payment(text: str, *, customer_hint: str | None = None) -> Payment:
    amount_match = AMOUNT_RE.search(text)
    ref_match = REF_RE.search(text)
    confidence = 0.8 if amount_match else 0.35
    if ref_match:
        confidence += 0.1
    return Payment(
        id=f"pay_{uuid4().hex[:12]}",
        customer_id=customer_hint,
        amount=float(amount_match.group("amount")) if amount_match else 0,
        date=date.today(),
        reference=ref_match.group("ref") if ref_match else None,
        confidence=min(confidence, 0.95),
        status="pending_approval",
    )


def match_payment(
    text: str,
    *,
    client_id: str,
    repository: BusinessRepository,
    approvals: ApprovalService,
    customer_hint: str | None = None,
) -> Payment:
    payment = repository.upsert_payment(extract_payment(text, customer_hint=customer_hint))
    approvals.create_approval_request(
        client_id=client_id,
        action_type="mark_payment_received",
        proposed_action="Mark payment as received after owner confirmation",
        data={
            "payment_id": payment.id,
            "customer": payment.customer_id,
            "amount": payment.amount,
            "reference": payment.reference,
        },
        reason="Payment and ledger updates always require approval in the MVP.",
        source="payment_match",
        confidence=payment.confidence,
        risk_level=RiskLevel.high,
    )
    return payment

