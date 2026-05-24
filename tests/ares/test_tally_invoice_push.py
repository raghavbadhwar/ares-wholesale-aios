"""Tests for Tally invoice/payment/ledger/stock push and pull functions."""

from __future__ import annotations

import pytest

from apps.ares.ares.connectors.tally_sync_adapter import (
    push_invoices_to_tally,
    push_payments_to_tally,
    pull_ledger_from_tally,
    push_stock_items_to_tally,
    TALLY_BRIDGE_ADAPTER_LIMITATION,
)

_COMPANY = "Test Trading Co"
_INVOICES = [
    {
        "invoice_number": "INV-001",
        "date": "20240101",
        "customer_id": "CUST-A",
        "amount": 11800.0,
        "total_amount": 11800.0,
    }
]
_PAYMENTS = [
    {
        "payment_id": "PAY-001",
        "date": "20240101",
        "customer_id": "CUST-A",
        "amount": 11800.0,
        "mode": "UPI",
    }
]
_STOCK_ITEMS = [
    {"name": "Widget Alpha", "unit": "NOS", "quantity": 100},
    {"name": "Widget Beta", "unit": "KG", "opening_stock": 50},
]


class TestPushInvoicesToTally:
    def test_local_fallback_no_gateway(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_invoices_to_tally(invoices=_INVOICES, company_name=_COMPANY)
        assert result["mode"] == "local_contract_mock"
        assert result["live_called"] is False
        assert result["limitation"] == TALLY_BRIDGE_ADAPTER_LIMITATION

    def test_empty_invoices_list(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_invoices_to_tally(invoices=[], company_name=_COMPANY)
        assert result["invoices_submitted"] == 0
        assert result["invoices_pushed"] == 0

    def test_company_name_in_result(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_invoices_to_tally(invoices=_INVOICES, company_name=_COMPANY)
        assert result["company_name"] == _COMPANY

    def test_audit_fields_present(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_invoices_to_tally(invoices=_INVOICES, company_name=_COMPANY)
        audit = result["audit"]
        assert "live_tally_push" in audit
        assert "company_mutation_performed" in audit
        assert "credential_values_inspected" in audit
        assert audit["credential_values_inspected"] is False

    def test_invoices_submitted_matches_input(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_invoices_to_tally(invoices=_INVOICES * 3, company_name=_COMPANY)
        assert result["invoices_submitted"] == 3


class TestPushPaymentsToTally:
    def test_local_fallback_no_gateway(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_payments_to_tally(payments=_PAYMENTS, company_name=_COMPANY)
        assert result["mode"] == "local_contract_mock"
        assert result["live_called"] is False

    def test_empty_payments_list(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_payments_to_tally(payments=[], company_name=_COMPANY)
        assert result["payments_submitted"] == 0
        assert result["payments_pushed"] == 0

    def test_payments_submitted_matches_input(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_payments_to_tally(payments=_PAYMENTS * 2, company_name=_COMPANY)
        assert result["payments_submitted"] == 2

    def test_audit_fields_present(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_payments_to_tally(payments=_PAYMENTS, company_name=_COMPANY)
        audit = result["audit"]
        assert "live_tally_push" in audit
        assert "company_mutation_performed" in audit


class TestPullLedgerFromTally:
    def test_local_fallback_no_gateway(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = pull_ledger_from_tally(
            company_name=_COMPANY, from_date="20240101", to_date="20240131"
        )
        assert result["mode"] == "local_contract_mock"
        assert result["live_called"] is False
        assert result["entries"] == []

    def test_dates_in_result(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = pull_ledger_from_tally(
            company_name=_COMPANY, from_date="20240101", to_date="20240131"
        )
        assert result["from_date"] == "20240101"
        assert result["to_date"] == "20240131"

    def test_default_ledger_name(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = pull_ledger_from_tally(
            company_name=_COMPANY, from_date="20240101", to_date="20240131"
        )
        assert result["ledger_name"] == "All Ledgers"

    def test_entries_pulled_is_zero_in_mock(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = pull_ledger_from_tally(
            company_name=_COMPANY, from_date="20240101", to_date="20240131"
        )
        assert result["entries_pulled"] == 0


class TestPushStockItemsToTally:
    def test_local_fallback_no_gateway(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_stock_items_to_tally(stock_items=_STOCK_ITEMS, company_name=_COMPANY)
        assert result["mode"] == "local_contract_mock"
        assert result["live_called"] is False

    def test_items_submitted_matches_input(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_stock_items_to_tally(stock_items=_STOCK_ITEMS, company_name=_COMPANY)
        assert result["items_submitted"] == 2

    def test_empty_stock_list(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_stock_items_to_tally(stock_items=[], company_name=_COMPANY)
        assert result["items_submitted"] == 0
        assert result["items_pushed"] == 0

    def test_audit_fields_present(self, monkeypatch):
        monkeypatch.delenv("TALLY_BUSY_SANDBOX_XML_GATEWAY_URL", raising=False)
        result = push_stock_items_to_tally(stock_items=_STOCK_ITEMS, company_name=_COMPANY)
        audit = result["audit"]
        assert "live_tally_push" in audit
        assert "company_mutation_performed" in audit
        assert "credential_values_inspected" in audit
