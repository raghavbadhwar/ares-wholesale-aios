from __future__ import annotations

from datetime import datetime
from pathlib import Path

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.connectors.export_parser import parse_outstanding_report, parse_stock_report
from apps.ares.ares.connectors.google_drive import DriveFile, GoogleDriveWatcher
from apps.ares.ares.connectors.message_ingest import ingest_forwarded_message
from apps.ares.ares.data.models import Invoice, StockRecord
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.orchestrator.intent_classifier import EventIntent, classify_event, classify_text
from apps.ares.ares.orchestrator.router import AresRouter, WORKFLOW_ALIASES, route_text


class FakeDrive:
    def list_files(self, folder_id: str) -> list[DriveFile]:
        assert folder_id == "folder_1"
        return [
            DriveFile(id="a", name="invoice.pdf", mime_type="application/pdf"),
            DriveFile(id="b", name="stock.csv", mime_type="text/csv"),
        ]


def test_forwarded_message_becomes_event_and_classifies_order() -> None:
    event = ingest_forwarded_message(
        client_id="demo",
        sender="Raj Traders",
        message_text="Raj Traders 20 carton Surf kal bhejna",
        timestamp=datetime(2026, 1, 1),
    )

    assert event.source == "message_forward"
    assert classify_event(event) == EventIntent.new_order


def test_drive_watcher_emits_only_new_files() -> None:
    watcher = GoogleDriveWatcher(FakeDrive())

    events = watcher.list_new_files(client_id="demo", folder_id="folder_1", seen_file_ids={"a"})

    assert len(events) == 1
    assert events[0].file_id == "b"
    assert classify_event(events[0]) == EventIntent.export_file


def test_csv_export_parsers(tmp_path: Path) -> None:
    outstanding = tmp_path / "outstanding.csv"
    outstanding.write_text(
        "id,invoice_number,customer_id,amount,due_date,status\n"
        "inv_1,INV-1,cust_1,25000,2026-01-01,overdue\n",
        encoding="utf-8",
    )
    stock = tmp_path / "stock.csv"
    stock.write_text(
        "sku_id,name,current_stock,reorder_level,unit\n"
        "surf,Surf,4,10,carton\n",
        encoding="utf-8",
    )

    assert parse_outstanding_report(outstanding)[0].amount == 25000
    assert parse_stock_report(stock)[0].current_stock == 4


def test_router_maps_common_hinglish_commands() -> None:
    assert route_text("Aaj ka payment batao") == "payment-radar"
    assert route_text("Low stock kya hai?") == "stock-radar"
    assert classify_text("Payment done UTR 123456") == EventIntent.payment_update


def test_router_runs_workflow_with_available_data() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[
            Invoice(
                id="inv_1",
                invoice_number="INV-1",
                customer_id="cust_1",
                amount=10000,
                status="overdue",
            )
        ],
        stock_records=[StockRecord(sku_id="surf", name="Surf", current_stock=2, reorder_level=10)],
    )
    approvals = ApprovalService(repo)
    router = AresRouter(repo, approvals, client_id="demo")

    result = router.handle("daily brief")

    assert result["workflow"] == "daily-brief"
    assert "Ares Brief" in result["message"]
    assert result["payload"]["pending_approvals"] == 0
    assert result["payload"]["payments"]["priorities"]


def test_router_workflow_registry_includes_executable_order_capture() -> None:
    assert "order-capture" in WORKFLOW_ALIASES
    assert route_text("pending orders dikhao") == "order-capture"
