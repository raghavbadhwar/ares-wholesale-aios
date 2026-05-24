"""Payment gateway webhook receiver for Ares.

Handles inbound webhooks from:
  - Razorpay   POST /ares/webhook/payment/razorpay
  - Cashfree   POST /ares/webhook/payment/cashfree
  - PhonePe    POST /ares/webhook/payment/phonepe

All payment gateways require a 200 response to stop retrying, so all
endpoints return 200 even on processing errors.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["ares-payments"])

_SUPPORTED_PROVIDERS = frozenset({"razorpay", "cashfree", "phonepe"})

# Provider-specific signing secret env vars
_PROVIDER_SECRET_ENV: dict[str, str] = {
    "razorpay": "RAZORPAY_WEBHOOK_SIGNING_SECRET",
    "cashfree": "CASHFREE_WEBHOOK_SIGNING_SECRET",
    "phonepe": "PHONEPE_WEBHOOK_SIGNING_SECRET",
}


@router.post("/ares/webhook/payment/{provider}")
async def payment_receive(provider: str, request: Request) -> Any:
    """Receive payment events from Razorpay, Cashfree, or PhonePe.

    Payment gateways retry on non-200 responses, so we always return 200
    even when processing fails. The `provider` path parameter selects the
    normalizer inside the payment gateway sandbox connector.
    """
    if provider not in _SUPPORTED_PROVIDERS:
        return Response(
            content=json.dumps({"status": "not_found", "provider": provider}),
            media_type="application/json",
            status_code=404,
        )

    raw_body = await request.body()
    headers = dict(request.headers)

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[ares/payment/{provider}] Invalid JSON payload: {exc}", file=sys.stderr)
        return {"status": "error", "provider": provider, "detail": "invalid_json"}

    webhook_signing_secret = os.getenv(_PROVIDER_SECRET_ENV.get(provider, ""), None)

    try:
        from apps.ares.ares.connectors.payment_gateway_sandbox import (
            ingest_payment_gateway_sandbox_payload,
        )

        # Repository and approvals are not available at the gateway layer;
        # the connector handles the None case gracefully (local mock mode)
        result = ingest_payment_gateway_sandbox_payload(
            repository=None,  # type: ignore[arg-type]
            approvals=None,  # type: ignore[arg-type]
            client_id="webhook",
            provider=provider,
            payload=payload,
            headers=headers,
            webhook_signing_secret=webhook_signing_secret,
        )
        ingested = result.get("payments_ingested", 0)
    except Exception as exc:
        print(f"[ares/payment/{provider}] Ingest error: {exc}", file=sys.stderr)
        ingested = 0

    return {"status": "received", "provider": provider, "payments_ingested": ingested}
