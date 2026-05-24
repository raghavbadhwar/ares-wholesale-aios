"""Tests for the WhatsApp webhook receiver (gateway/whatsapp_webhook.py)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.ares.ares.gateway.whatsapp_webhook import router


@pytest.fixture()
def app():
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture()
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Hub challenge verification (GET)
# ---------------------------------------------------------------------------

class TestWhatsAppVerify:
    def test_correct_token_returns_challenge(self, client, monkeypatch):
        monkeypatch.setenv("META_WABA_SANDBOX_WEBHOOK_VERIFY_TOKEN", "test_token_xyz")
        resp = client.get(
            "/ares/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test_token_xyz",
                "hub.challenge": "challenge_abc123",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "challenge_abc123"

    def test_wrong_token_returns_403(self, client, monkeypatch):
        monkeypatch.setenv("META_WABA_SANDBOX_WEBHOOK_VERIFY_TOKEN", "correct_token")
        resp = client.get(
            "/ares/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "irrelevant",
            },
        )
        assert resp.status_code == 403

    def test_missing_token_env_returns_403(self, client, monkeypatch):
        monkeypatch.delenv("META_WABA_SANDBOX_WEBHOOK_VERIFY_TOKEN", raising=False)
        resp = client.get(
            "/ares/webhook/whatsapp",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "anything",
                "hub.challenge": "c",
            },
        )
        assert resp.status_code == 403

    def test_wrong_mode_returns_403(self, client, monkeypatch):
        monkeypatch.setenv("META_WABA_SANDBOX_WEBHOOK_VERIFY_TOKEN", "tok")
        resp = client.get(
            "/ares/webhook/whatsapp",
            params={
                "hub.mode": "unsubscribe",
                "hub.verify_token": "tok",
                "hub.challenge": "c",
            },
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Inbound message processing (POST)
# ---------------------------------------------------------------------------

def _sign(body: bytes, secret: str) -> str:
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256)
    return "sha256=" + mac.hexdigest()


class TestWhatsAppReceive:
    _MINIMAL_PAYLOAD = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "91XXXXXXXXXX", "phone_number_id": "PHID"},
                            "messages": [],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }

    def test_valid_signature_returns_200(self, client, monkeypatch):
        monkeypatch.setenv("META_WABA_SANDBOX_APP_SECRET", "test_secret")
        body = json.dumps(self._MINIMAL_PAYLOAD).encode()
        sig = _sign(body, "test_secret")
        resp = client.post(
            "/ares/webhook/whatsapp",
            content=body,
            headers={"x-hub-signature-256": sig, "content-type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "received"

    def test_invalid_signature_returns_401(self, client, monkeypatch):
        monkeypatch.setenv("META_WABA_SANDBOX_APP_SECRET", "correct_secret")
        body = json.dumps(self._MINIMAL_PAYLOAD).encode()
        resp = client.post(
            "/ares/webhook/whatsapp",
            content=body,
            headers={"x-hub-signature-256": "sha256=bad", "content-type": "application/json"},
        )
        assert resp.status_code == 401

    def test_no_secret_configured_skips_verification(self, client, monkeypatch):
        """If no APP_SECRET is configured we skip signature check and process normally."""
        monkeypatch.delenv("META_WABA_SANDBOX_APP_SECRET", raising=False)
        body = json.dumps(self._MINIMAL_PAYLOAD).encode()
        resp = client.post(
            "/ares/webhook/whatsapp",
            content=body,
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 200

    def test_invalid_json_returns_error(self, client, monkeypatch):
        monkeypatch.delenv("META_WABA_SANDBOX_APP_SECRET", raising=False)
        resp = client.post(
            "/ares/webhook/whatsapp",
            content=b"not json at all",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 200  # Always 200 to stop Meta retrying
        data = resp.json()
        assert data["status"] == "error"
        assert data["detail"] == "invalid_json"
