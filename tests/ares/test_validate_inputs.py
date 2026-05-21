from __future__ import annotations

from pathlib import Path

import pytest

from apps.ares.ares.cli import main
from apps.ares.ares.connectors.export_parser import UnsupportedExportError, parse_outstanding_report, parse_stock_report
from apps.ares.ares.profiles import ClientProfile, write_client_profile


def test_outstanding_parser_reports_missing_required_columns(tmp_path: Path) -> None:
    path = tmp_path / "bad_outstanding.csv"
    path.write_text("invoice_number,due_date,status\nINV-1,2026-01-01,overdue\n", encoding="utf-8")

    with pytest.raises(UnsupportedExportError, match="Missing required columns for outstanding export"):
        parse_outstanding_report(path)


def test_stock_parser_reports_zero_valid_rows(tmp_path: Path) -> None:
    path = tmp_path / "stock_export.csv"
    path.write_text("sku_id,name,current_stock,reorder_level\n,,,\n", encoding="utf-8")

    with pytest.raises(UnsupportedExportError, match="No valid stock rows found"):
        parse_stock_report(path)


def test_validate_inputs_reports_empty_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    monkeypatch.setattr("sys.argv", ["ares", "validate-inputs", "--client", "demo"])

    assert main() == 0
    output = capsys.readouterr().out

    assert "No export files found" in output
    assert "No inbox messages found" in output
    assert "Blocking issues: 0" in output


def test_validate_inputs_reports_parseable_and_unparseable_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    root = tmp_path / ".ares" / "clients" / "demo"
    (root / "exports" / "tally_outstanding.csv").write_text(
        "id,invoice_number,customer_id,amount,status\ninv_1,INV-1,Raj,1200,overdue\n",
        encoding="utf-8",
    )
    (root / "exports" / "bad_stock.csv").write_text(
        "sku_id,name\nsurf,Surf\n",
        encoding="utf-8",
    )
    (root / "inbox" / "order_1.txt").write_text("Raj 5 box Surf kal bhejna", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["ares", "validate-inputs", "--client", "demo"])

    assert main() == 1
    output = capsys.readouterr().out

    assert "Parseable exports: 1" in output
    assert "Unparseable exports: 1" in output
    assert "Inbox messages: 1" in output
    assert "bad_stock.csv" in output
    assert "Missing required columns for stock export" in output
