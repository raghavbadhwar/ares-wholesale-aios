"""WhatsApp Business webhook receiver for Ares.

Provides two HTTP endpoints that Meta calls:
  GET  /ares/webhook/whatsapp  — webhook verification (hub challenge handshake)
  POST /ares/webhook/whatsapp  — inbound message and delivery receipt events
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
from typing import Any

from fastapi import APIRouter, Request, Response

from apps.ares.ares.connectors.whatsapp_sandbox import ingest_whatsapp_sandbox_webhook

router = APIRouter(tags=["ares-whatsapp"])


@router.get("/ares/webhook/whatsapp")
async def whatsapp_verify(request: Request) -> Response:
    """Meta webhook verification — responds to the hub.challenge handshake.

    Meta sends a GET with hub.mode=subscribe, hub.verify_token, and
    hub.challenge. We must return hub.challenge as plain text if the
    verify_token matches our configured secret.
    """
    params = dict(request.query_params)
    mode = params.get("hub.mode", "")
    verify_token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    expected_token = os.getenv("META_WABA_SANDBOX_WEBHOOK_VERIFY_TOKEN", "")

    if mode == "subscribe" and verify_token and expected_token and verify_token == expected_token:
        return Response(content=challenge, media_type="text/plain", status_code=200)

    return Response(content="Forbidden", status_code=403)


@router.post("/ares/webhook/whatsapp")
async def whatsapp_receive(request: Request) -> dict[str, Any]:
    """Receive inbound WhatsApp messages and delivery receipts from Meta.

    Meta requires a 200 response to stop retrying, so we always return 200.
    Signature verification failures are logged but still return 200 to
    prevent Meta from disabling the webhook.
    """
    raw_body = await request.body()
    headers = dict(request.headers)

    # Verify HMAC-SHA256 signature from Meta
    app_secret = os.getenv("META_WABA_SANDBOX_APP_SECRET", "")
    if app_secret:
        mac = hmac.new(
            app_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        )
        expected_sig = "sha256=" + mac.hexdigest()
        received_sig = headers.get("x-hub-signature-256", "")
        if not hmac.compare_digest(expected_sig, received_sig):
            # Log but return 401 (Meta will retry; we want to catch misconfiguration)
            print(
                "[ares/whatsapp] Signature mismatch — possible replay attack or wrong secret.",
                file=sys.stderr,
            )
            return Response(content="Unauthorized", status_code=401)  # type: ignore[return-value]

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError) as exc:
        print(f"[ares/whatsapp] Invalid JSON payload: {exc}", file=sys.stderr)
        # Return 200 to stop Meta retrying a permanently malformed payload
        return {"status": "error", "detail": "invalid_json"}

    try:
        # Use a minimal repository for webhook processing (no client context yet)
        # The webhook normalizer can work without a repository for basic ingestion
        result = ingest_whatsapp_sandbox_webhook(
            repository=None,  # type: ignore[arg-type]
            client_id="webhook",
            payload=payload,
            headers=headers,
            webhook_app_secret=app_secret or None,
        )
        ingested = len(result.get("messages", []))
    except Exception as exc:
        print(f"[ares/whatsapp] Ingest error: {exc}", file=sys.stderr)
        ingested = 0

    return {"status": "received", "events_ingested": ingested}
