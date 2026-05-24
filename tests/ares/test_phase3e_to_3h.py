"""Tests for Phase 3E-3H — logistics, mandi, AA, and ONDC integrations (local mode)."""

from __future__ import annotations

import pytest

from apps.ares.ares.workflows.logistics import (
    integrate_delhivery_sandbox,
    integrate_shiprocket_sandbox,
)
from apps.ares.ares.workflows.mandi_prices import (
    fetch_agmarknet_prices,
)
from apps.ares.ares.workflows.account_aggregator import (
    initiate_aa_consent_request,
    poll_aa_data_session,
)
from apps.ares.ares.workflows.ondc_seller import (
    publish_ondc_catalogue_via_beckn,
    acknowledge_ondc_order_via_beckn,
    _beckn_context,
)


# ---------------------------------------------------------------------------
# Phase 3E — Delhivery sandbox (local mode, no API token)
# ---------------------------------------------------------------------------

def test_delhivery_local_mode_no_token():
    result = integrate_delhivery_sandbox(
        shipment={"invoice_id": "INV001", "customer_name": "Raj Traders"},
    )
    assert result["mode"] == "local_contract_mock"
    assert result["live_called"] is False
    assert result["limitation"] is not None
    assert result["audit"]["carrier_api_called"] is False


def test_delhivery_local_mode_waybill_is_none():
    result = integrate_delhivery_sandbox(
        shipment={"invoice_id": "INV001"},
    )
    assert result["waybill"] is None


def test_delhivery_local_mode_status_is_mock_pending():
    result = integrate_delhivery_sandbox(
        shipment={"invoice_id": "INV001"},
    )
    assert result["status"] == "mock_pending"


# ---------------------------------------------------------------------------
# Phase 3E — Shiprocket sandbox (local mode, no credentials)
# ---------------------------------------------------------------------------

def test_shiprocket_local_mode_no_creds():
    result = integrate_shiprocket_sandbox(
        order={"invoice_id": "INV002", "customer_name": "Patel Store"},
    )
    assert result["mode"] == "local_contract_mock"
    assert result["live_called"] is False
    assert result["audit"]["carrier_api_called"] is False


def test_shiprocket_local_mode_order_id_is_none():
    result = integrate_shiprocket_sandbox(
        order={"invoice_id": "INV002"},
    )
    assert result["order_id"] is None
    assert result["shipment_id"] is None


def test_shiprocket_local_ref_preserved():
    result = integrate_shiprocket_sandbox(
        order={"invoice_id": "INV002"},
    )
    assert result["order_ref"] == "INV002"


# ---------------------------------------------------------------------------
# Phase 3F — Agmarknet (local mode, no API key)
# ---------------------------------------------------------------------------

def test_agmarknet_local_mode_no_key():
    result = fetch_agmarknet_prices(commodity="Wheat")
    assert result["mode"] == "local_simulation"
    assert result["agmarknet_api_called"] is False
    assert result["price_snapshots"] == []
    assert result["limitation"] is not None


def test_agmarknet_local_mode_with_state():
    result = fetch_agmarknet_prices(commodity="Onion", state="Maharashtra")
    assert result["commodity"] == "Onion"
    assert result["state"] == "Maharashtra"


def test_agmarknet_records_returned_zero_local():
    result = fetch_agmarknet_prices(commodity="Rice")
    assert result["records_returned"] == 0


# ---------------------------------------------------------------------------
# Phase 3G — Sahamati AA (local mode, no credentials)
# ---------------------------------------------------------------------------

def test_aa_consent_local_mode_no_creds():
    result = initiate_aa_consent_request(
        customer_phone="9876543210",
        customer_id="cust_001",
    )
    assert result["mode"] == "local_simulation"
    assert result["aa_network_called"] is False
    assert result["consent_handle"] is not None
    assert result["consent_handle"].startswith("aa_handle_")


def test_aa_consent_status_simulated_pending():
    result = initiate_aa_consent_request(
        customer_phone="9876543210",
        customer_id="cust_001",
    )
    assert result["consent_status"] == "simulated_pending"


def test_aa_consent_limitation_present():
    result = initiate_aa_consent_request(
        customer_phone="9876543210",
        customer_id="cust_001",
    )
    assert result["limitation"] is not None


def test_poll_aa_data_session_local_mode():
    result = poll_aa_data_session(consent_handle="aa_handle_test1234")
    assert result["mode"] == "local_simulation"
    assert result["consent_status"] == "PENDING"
    assert result["aa_network_called"] is False


# ---------------------------------------------------------------------------
# Phase 3H — ONDC Beckn (local mode, no gateway URL)
# ---------------------------------------------------------------------------

def test_beckn_context_structure():
    ctx = _beckn_context(action="on_search", subscriber_id="seller.example.com")
    assert ctx["action"] == "on_search"
    assert ctx["domain"] == "nic2004:52110"
    assert ctx["country"] == "IND"
    assert "transaction_id" in ctx
    assert "message_id" in ctx


def test_beckn_context_custom_transaction_id():
    ctx = _beckn_context(action="on_confirm", subscriber_id="seller.com", transaction_id="txn_custom")
    assert ctx["transaction_id"] == "txn_custom"


class _StubProductSKU:
    def __init__(self):
        self.id = "sku_001"
        self.name = "Parle-G 100g"
        self.category = "biscuits"
        self.current_stock = 500
        self.unit = "pcs"
        self.selling_price = 10.0


class _StubRepo:
    def get_products(self):
        return [_StubProductSKU()]


def test_publish_ondc_catalogue_local_mode():
    repo = _StubRepo()
    result = publish_ondc_catalogue_via_beckn(
        repository=repo,
        seller_id="seller_test",
    )
    assert result["mode"] == "local_beckn_payload"
    assert result["ondc_network_called"] is False
    assert result["items_published"] == 1
    assert "beckn_payload" in result


def test_publish_ondc_catalogue_payload_structure():
    repo = _StubRepo()
    result = publish_ondc_catalogue_via_beckn(
        repository=repo,
        seller_id="seller_test",
    )
    payload = result["beckn_payload"]
    assert "context" in payload
    assert payload["context"]["action"] == "on_search"
    assert "catalog" in payload["message"]


def test_acknowledge_ondc_order_ack():
    result = acknowledge_ondc_order_via_beckn(
        ondc_order_id="ondc_ord_001",
        seller_id="seller_test",
        ack_status="ACK",
    )
    assert result["mode"] == "local_beckn_payload"
    assert result["ack_status"] == "ACK"
    assert result["ondc_network_called"] is False


def test_acknowledge_ondc_order_nack():
    result = acknowledge_ondc_order_via_beckn(
        ondc_order_id="ondc_ord_002",
        seller_id="seller_test",
        ack_status="NACK",
    )
    assert result["ack_status"] == "NACK"
    assert result["beckn_payload"]["message"]["order"]["state"] == "Cancelled"


def test_ondc_limitation_in_local_mode():
    repo = _StubRepo()
    result = publish_ondc_catalogue_via_beckn(
        repository=repo,
        seller_id="seller_test",
    )
    assert result["limitation"] is not None
