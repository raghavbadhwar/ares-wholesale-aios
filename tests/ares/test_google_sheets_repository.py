from __future__ import annotations

from apps.ares.ares.data.factory import create_repository_for_profile
from apps.ares.ares.profiles import ClientProfile, ConnectorStatus, GoogleWorkspaceConfig


class _FakeSheetsClient:
    def __init__(self) -> None:
        self.rows = {
            "Customers": [{"id": "cust_1", "name": "Raj Traders"}],
            "Stock": [{"sku_id": "sku_1", "name": "Soap", "current_stock": 10, "reorder_level": 2}],
            "Invoices": [{"id": "inv_1", "invoice_number": "INV-1", "customer_id": "cust_1", "amount": 11800, "status": "open"}],
            "PurchaseInvoices": [
                {
                    "id": "pinv_1",
                    "supplier_id": "sup_1",
                    "supplier_gstin": "27SUPPL1234F1Z5",
                    "invoice_number": "PINV-1",
                    "date": "2026-05-20",
                    "taxable_value": 8000,
                    "tax_amount": 1440,
                    "status": "booked",
                }
            ],
            "Payments": [{"id": "pay_1", "customer_id": "cust_1", "amount": 5000, "status": "reconciled"}],
        }

    def read_rows(self, spreadsheet_id: str, tab: str) -> list[dict]:
        assert spreadsheet_id == "sheet_123"
        return list(self.rows.get(tab, []))

    def append_row(self, spreadsheet_id: str, tab: str, row: dict) -> None:
        raise AssertionError("append_row should not be called in hydration test")


def test_factory_returns_hydrated_google_sheets_repository(monkeypatch) -> None:
    monkeypatch.setattr("apps.ares.ares.data.factory.GwsSheetsClient", _FakeSheetsClient)
    profile = ClientProfile(
        client_slug="demo",
        business_name="Demo Wholesale",
        owner_name="Owner",
        google=GoogleWorkspaceConfig(command_center_sheet_id="sheet_123"),
        connector_status=ConnectorStatus(google_sheets="configured"),
    )

    repo = create_repository_for_profile(profile)

    assert repo.get_customers()[0].id == "cust_1"
    assert repo.get_customers()[0].client_id == "demo"
    assert repo.get_outstanding()[0].invoice_number == "INV-1"
    assert repo.get_outstanding()[0].client_id == "demo"
    assert repo.get_outstanding()[0].source_file == "gsheets://sheet_123/Invoices/inv_1"
    assert repo.get_purchase_invoices()[0].invoice_number == "PINV-1"
    assert repo.get_purchase_invoices()[0].client_id == "demo"
    assert repo.get_purchase_invoices()[0].source_file == "gsheets://sheet_123/PurchaseInvoices/pinv_1"
    assert repo.get_payments()[0].id == "pay_1"
    assert repo.get_payments()[0].client_id == "demo"
