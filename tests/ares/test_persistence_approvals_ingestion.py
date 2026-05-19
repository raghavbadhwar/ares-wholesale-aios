from __future__ import annotations

from pathlib import Path

from apps.ares.ares.approvals.service import ApprovalService
from apps.ares.ares.cli import main
from apps.ares.ares.connectors.file_ingest import ingest_export_file
from apps.ares.ares.connectors.message_ingest import ingest_forwarded_message
from apps.ares.ares.data.json_repository import JsonClientRepository
from apps.ares.ares.data.models import BusinessMemory, Invoice, StockRecord
from apps.ares.ares.data.repository import InMemoryRepository
from apps.ares.ares.profiles import ClientProfile, write_client_profile
from apps.ares.ares.workflows.daily_brief import run_daily_brief
from apps.ares.ares.workflows.order_capture import capture_order, extract_order_result
from apps.ares.ares.workflows.payment_radar import run_payment_radar


def test_json_repository_persists_business_records(tmp_path: Path) -> None:
    repo = JsonClientRepository(tmp_path / "data")
    repo.upsert_invoice(Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj", amount=1200, status="overdue"))
    repo.upsert_stock_record(StockRecord(sku_id="surf", name="Surf", current_stock=2, reorder_level=10))

    reloaded = JsonClientRepository(tmp_path / "data")

    assert reloaded.get_outstanding()[0].invoice_number == "INV-1"
    assert reloaded.get_stock_records()[0].sku_id == "surf"


def test_cli_persists_csv_import_between_runs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    outstanding = tmp_path / "outstanding.csv"
    outstanding.write_text(
        "id,invoice_number,customer_id,amount,status\ninv_1,INV-1,Raj Traders,10000,overdue\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "sys.argv",
        ["ares", "run-workflow", "--client", "demo", "--workflow", "payment-radar", "--outstanding-csv", str(outstanding)],
    )
    assert main() == 0
    capsys.readouterr()

    monkeypatch.setattr("sys.argv", ["ares", "run-workflow", "--client", "demo", "--workflow", "payment-radar", "--json"])
    assert main() == 0
    payload = capsys.readouterr().out
    assert '"total_outstanding": 10000.0' in payload


def test_payment_radar_approval_requests_are_idempotent() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj", amount=10000, status="overdue")]
    )
    approvals = ApprovalService(repo)

    run_payment_radar(repo, approvals, client_id="demo")
    run_payment_radar(repo, approvals, client_id="demo")

    assert len(repo.list_pending_approvals()) == 1
    assert repo.list_pending_approvals()[0].dedupe_key == "payment_reminder:inv_1"


def test_daily_brief_does_not_create_payment_approvals() -> None:
    repo = InMemoryRepository.from_records(
        invoices=[Invoice(id="inv_1", invoice_number="INV-1", customer_id="Raj", amount=10000, status="overdue")]
    )

    run_daily_brief(repo, ApprovalService(repo), client_id="demo")

    assert repo.list_pending_approvals() == []


def test_order_extraction_supports_hinglish_units_and_structured_uncertainty() -> None:
    event = ingest_forwarded_message(client_id="demo", sender="Raj Traders", message_text="Raj Traders 3 dabba Maggi aur 5 pkt Parle kal bhejna")

    result = extract_order_result(event)

    assert result.order.items[0].unit == "box"
    assert result.order.items[1].unit == "packet"
    assert result.needs_approval is False


def test_file_ingest_routes_outstanding_and_stock_exports(tmp_path: Path) -> None:
    repo = InMemoryRepository()
    outstanding = tmp_path / "tally_outstanding.csv"
    outstanding.write_text("id,invoice_number,customer_id,amount,status\ninv_1,INV-1,Raj,900,open\n", encoding="utf-8")
    stock = tmp_path / "stock_export.csv"
    stock.write_text("sku_id,name,current_stock,reorder_level\nsurf,Surf,2,10\n", encoding="utf-8")

    assert ingest_export_file(outstanding, repo)["kind"] == "outstanding"
    assert ingest_export_file(stock, repo)["kind"] == "stock"
    assert repo.get_outstanding()[0].amount == 900
    assert repo.get_stock_records()[0].sku_id == "surf"


def test_unclear_order_uses_confirm_action_and_dedupe_key() -> None:
    repo = InMemoryRepository()
    approvals = ApprovalService(repo)
    event = ingest_forwarded_message(client_id="demo", sender="Raj", message_text="same maal bhej dena")

    order = capture_order(event, repo, approvals)
    capture_order(event, repo, approvals)

    assert order.confidence < 0.75
    assert len(repo.list_pending_approvals()) == 1
    assert repo.list_pending_approvals()[0].type == "confirm_unclear_order"
