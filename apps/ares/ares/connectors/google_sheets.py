"""Google Sheets-backed repository adapter shape for Ares.

The MVP keeps this dependency-injected so unit tests use fakes and no live
Google credentials are required.
"""

from __future__ import annotations

from typing import Protocol

from apps.ares.ares.data.models import ApprovalRequest, Customer, Invoice, StockRecord
from apps.ares.ares.data.repository import InMemoryRepository


class SheetsClient(Protocol):
    def read_rows(self, spreadsheet_id: str, tab: str) -> list[dict]: ...

    def append_row(self, spreadsheet_id: str, tab: str, row: dict) -> None: ...


TAB_NAMES = [
    "Dashboard",
    "Customers",
    "Products",
    "Orders",
    "Payments",
    "Stock",
    "Suppliers",
    "Tasks",
    "Approvals",
    "Business Rules",
    "Memory Notes",
    "Workflow Runs",
]


class GoogleSheetsRepository(InMemoryRepository):
    """Thin adapter over a provided Sheets client.

    The adapter mirrors records into memory for deterministic workflow runs.
    A production connector can replace this with range updates without changing
    workflow code because workflows depend on BusinessRepository.
    """

    def __init__(self, *, client: SheetsClient, spreadsheet_id: str) -> None:
        super().__init__()
        self.client = client
        self.spreadsheet_id = spreadsheet_id

    def load_customers(self) -> list[Customer]:
        for row in self.client.read_rows(self.spreadsheet_id, "Customers"):
            self.upsert_customer(Customer.model_validate(row))
        return self.get_customers()

    def load_stock(self) -> list[StockRecord]:
        for row in self.client.read_rows(self.spreadsheet_id, "Stock"):
            self.upsert_stock_record(StockRecord.model_validate(row))
        return self.get_stock_records()

    def load_outstanding(self) -> list[Invoice]:
        for row in self.client.read_rows(self.spreadsheet_id, "Payments"):
            if row.get("amount"):
                self.upsert_invoice(Invoice.model_validate(row))
        return self.get_outstanding()

    def create_approval(self, approval: ApprovalRequest) -> ApprovalRequest:
        saved = super().create_approval(approval)
        self.client.append_row(self.spreadsheet_id, "Approvals", saved.model_dump(mode="json"))
        return saved

