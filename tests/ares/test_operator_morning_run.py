from __future__ import annotations

from pathlib import Path

import pytest

from apps.ares.ares.cli import main
from apps.ares.ares.profiles import ClientProfile, write_client_profile


def test_morning_run_outputs_actionable_operator_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("ARES_HOME", str(tmp_path / ".ares"))
    write_client_profile(ClientProfile(client_slug="demo", business_name="Demo", owner_name="Owner"))
    root = tmp_path / ".ares" / "clients" / "demo"
    (root / "exports" / "tally_outstanding.csv").write_text(
        "id,invoice_number,customer_id,amount,due_date,status\n"
        "inv_1,INV-1,Raj,1200,2026-01-01,overdue\n",
        encoding="utf-8",
    )
    (root / "exports" / "stock_export.csv").write_text(
        "sku_id,name,current_stock,reorder_level\nsurf,Surf,2,10\n",
        encoding="utf-8",
    )
    (root / "inbox" / "order_1.txt").write_text("Raj 5 box Surf kal bhejna", encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["ares", "morning-run", "--client", "demo"])

    assert main() == 0
    output = capsys.readouterr().out

    assert "Ares morning run for demo" in output
    assert "Files ingested: 3" in output
    assert "Overdue invoices: 1" in output
    assert "Low-stock items: 1" in output
    assert "Approvals created: 1" in output
    assert "Owner message:" in output
    assert "Ares approvals pending" in output or "Approval needed" in output


def test_morning_run_json_contains_operator_and_owner_payloads(
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
    monkeypatch.setattr("sys.argv", ["ares", "morning-run", "--client", "demo", "--json"])

    assert main() == 0
    output = capsys.readouterr().out

    assert '"client_id": "demo"' in output
    assert '"daily_brief"' in output
    assert '"owner_message"' in output
