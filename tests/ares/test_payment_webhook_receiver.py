"""Tests for the payment gateway webhook receiver (gateway/payment_webhook.py)."""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.ares.ares.gateway.payment_webhook import router

_RAZORPAY_PAYLOAD = {
    "entity": "event",
    "account_id": "acc_test",
    "event": "payment.captured",
    "contains": ["payment"],
    "payload": {
        "payment": {
            "entity": {
                "id": "pay_test123",
                "entity": "payment",
                "amount": 100000,
                "currency": "INR",
                "status": "captured",
                "order_id": "order_xyz",
                "method": "upi",
            }
        }
    },
}

_CASHFREE_PAYLOAD = {
    "data": {
        "payment": {
            "cf_payment_id": 1234567,
            "order_id": "cf_order_abc",
            "payment_status": "SUCCESS",
            "payment_amount": 500.0,
            "payment_currency": "INR",
        }
    },
    "event_time": "2024-01-01T09:00:00Z",
    "type": "PAYMENT_SUCCESS_WEBHOOK",
}

_PHONEPE_PAYLOAD = {
    "merchantId": "MXXX",
    "merchantTransactionId": "MT123",
    "transactionId": "T123",
    "amount": 25000,
    "state": "COMPLETED",
    "responseCode": "SUCCESS",
}


@pytest.fixture()
def app():
    application = FastAPI()
    application.include_router(router)
    return application


@pytest.fixture()
def client(app):
    return TestClient(app)


class TestPaymentWebhookReceiver:
    def _post(self, client, provider: str, payload: dict):
        return client.post(
            f"/ares/webhook/payment/{provider}",
            content=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
        )

    def test_razorpay_returns_200(self, client):
        resp = self._post(client, "razorpay", _RAZORPAY_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "received"
        assert data["provider"] == "razorpay"

    def test_cashfree_returns_200(self, client):
        resp = self._post(client, "cashfree", _CASHFREE_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "received"
        assert data["provider"] == "cashfree"

    def test_phonepe_returns_200(self, client):
        resp = self._post(client, "phonepe", _PHONEPE_PAYLOAD)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "received"
        assert data["provider"] == "phonepe"

    def test_unknown_provider_returns_404(self, client):
        resp = self._post(client, "paytm", {})
        assert resp.status_code == 404

    def test_invalid_json_returns_200_with_error(self, client):
        resp = client.post(
            "/ares/webhook/payment/razorpay",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"

    def test_response_has_payments_ingested_field(self, client):
        resp = self._post(client, "razorpay", _RAZORPAY_PAYLOAD)
        data = resp.json()
        assert "payments_ingested" in data
